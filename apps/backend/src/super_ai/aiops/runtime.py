"""可恢复的 LangGraph AIOps 诊断运行时。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol, TypedDict, cast
from uuid import uuid4

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel

from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.aiops.cls_tool_adapters import (
    ClsSearchLogHit,
    SearchLogInput,
    build_describe_log_context_input,
    build_text_to_search_log_query_input,
)
from super_ai.aiops.evidence import knowledge_evidence, normalize_tool_evidence
from super_ai.aiops.evidence_policy import evaluate_claim_evidence
from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticReportRecord,
    DiagnosticStepRecord,
    NewEvidence,
    PlanStep,
)
from super_ai.aiops.planning import (
    MAX_REPLANS,
    DiagnosticModel,
    PlanDraft,
    SearchLogQueryDefaults,
    create_validated_plan,
    find_search_log_tool,
    is_log_context_tool,
    is_query_builder_tool,
    is_search_log_tool,
    normalize_search_log_arguments,
    summarize_evidence,
    validate_plan,
)
from super_ai.aiops.reporting import build_fallback_report, validate_report
from super_ai.aiops.tool_adapters import (
    ensure_core_tool_schema_compatible,
    validate_runtime_tool_input,
)
from super_ai.aiops.tool_failures import (
    ToolConfigurationError,
    ToolEmptyResultError,
    ToolOutputValidationError,
    ToolSchemaIncompatibleError,
    classify_tool_failure,
)
from super_ai.aiops.tool_policy import (
    ToolCapabilityDescriptor,
    build_aiops_tool_registry,
    describe_builtin_knowledge_tool,
)
from super_ai.api_contracts import (
    ERROR_DEFINITIONS,
    SSE_ERROR_DATA_KEY,
    SSE_ERROR_TYPE,
    SSE_REFERENCE_SOURCE_TYPE,
    SSE_REPORT_TYPE,
    SSE_TASK_STATUS_TYPE,
    SSE_TOOL_CALL_TYPE,
    ErrorCode,
    KnowledgeRetrievalToolInput,
    KnowledgeRetrievalToolOutput,
)
from super_ai.api_responses import AppError
from super_ai.background_jobs.handlers import (
    BackgroundJobCancelledError,
    BackgroundJobContext,
    BackgroundJobHandler,
)
from super_ai.background_jobs.security import redact_error
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticStore
from super_ai.memory.primitives import dump_json, utc_now
from super_ai.project_config import JsonValue
from super_ai.retrieval.tool import create_knowledge_retrieval_tool
from super_ai.runtime.logging import log_lifecycle
from super_ai.tenancy.context import CurrentUser


class KnowledgeSource(Protocol):
    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput: ...


class DiagnosticToolResolver(Protocol):
    async def discover(
        self, owner_user_id: str, *, builtin_tool_names: frozenset[str]
    ) -> tuple[BaseTool, ...]: ...


class DiagnosticState(TypedDict):
    task_id: str
    next_position: int
    route: str
    last_error: str | None


def _route_after_replanner(state: DiagnosticState) -> str:
    return state["route"]


class DiagnosticRuntime:
    """每个 background job 调用创建一张有界 StateGraph 并持久化每个节点。"""

    def __init__(
        self,
        store: SqliteDiagnosticStore,
        knowledge: KnowledgeSource,
        tool_resolver: DiagnosticToolResolver,
        model: DiagnosticModel,
        auditor: AgentToolAuditService,
        *,
        secret_values: Sequence[str] = (),
        search_log_defaults: SearchLogQueryDefaults | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self._store = store
        self._knowledge = knowledge
        self._tool_resolver = tool_resolver
        self._model = model
        self._auditor = auditor
        self._secret_values = tuple(value for value in secret_values if value)
        self._search_log_defaults = search_log_defaults
        self._now_ms = now_ms or _current_time_ms

    def handler(self) -> BackgroundJobHandler:
        async def handle(context: BackgroundJobContext, payload: JsonValue) -> None:
            if not isinstance(payload, dict) or not isinstance(payload.get("taskId"), str):
                raise ValueError("aiops_diagnosis job payload 缺少 taskId")
            await self.run(context, cast(str, payload["taskId"]))

        return handle

    async def run(self, context: BackgroundJobContext, task_id: str) -> None:
        owner = context.owner_user_id
        log_lifecycle("aiops.diagnosis", resource_id=task_id, status="running")
        current_user = CurrentUser(owner)
        tools: dict[str, BaseTool] = {}
        tool_descriptors: dict[str, ToolCapabilityDescriptor] = {}

        async def emit(event_type: str, data: dict[str, object]) -> None:
            await self._store.call(
                "append_job_event", owner, context.job_id, event_type, cast(object, data)
            )

        async def checkpoint(node: str, state: DiagnosticState) -> None:
            task = await self._store.call("get_task", owner, task_id)
            evidence = await self._store.call("list_evidence", owner, task_id)
            payload: dict[str, JsonValue] = {
                "taskId": state["task_id"],
                "nextPosition": state["next_position"],
                "route": state["route"],
                "planVersion": task.plan_version if task is not None else 0,
                "replanCount": task.replan_count if task is not None else 0,
                "evidenceIds": [item.id for item in evidence],
            }
            if state.get("last_error") is not None:
                payload["lastError"] = state["last_error"]
            await self._store.call("save_checkpoint", owner, task_id, node, payload)

        async def planner(state: DiagnosticState) -> DiagnosticState:
            await context.raise_if_cancelled()
            task = await self._store.call("get_task", owner, task_id)
            if task is None:
                raise ValueError("诊断任务不存在")
            await self._store.call("transition_task", owner, task_id, "running")
            await emit(
                SSE_TASK_STATUS_TYPE,
                {"taskId": task_id, "status": "running", "message": "正在检索 SOP", "progress": 10},
            )
            if not task.current_plan:
                query = _diagnostic_query(task.query, task.alerts)
                retrieval_call_id = uuid4().hex
                retrieval_arguments: dict[str, JsonValue] = {"query": query, "topK": 5}
                await emit(
                    SSE_TOOL_CALL_TYPE,
                    {
                        "toolCallId": retrieval_call_id,
                        "toolName": "knowledge_retrieval",
                        "lifecycle": "started",
                        "input": {"argumentKeys": sorted(retrieval_arguments)},
                    },
                )

                async def retrieve_sop() -> KnowledgeRetrievalToolOutput:
                    return await self._knowledge.retrieve(
                        current_user, KnowledgeRetrievalToolInput(query=query, topK=5)
                    )

                try:
                    result = await self._auditor.execute(
                        current_user,
                        chat_session_id=None,
                        diagnostic_task_id=task_id,
                        tool_call_id=retrieval_call_id,
                        tool_name="knowledge_retrieval",
                        arguments=retrieval_arguments,
                        operation=retrieve_sop,
                    )
                except Exception as error:
                    safe = self._safe_message(error, retrieval_arguments)
                    await emit(
                        SSE_TOOL_CALL_TYPE,
                        {
                            "toolCallId": retrieval_call_id,
                            "toolName": "knowledge_retrieval",
                            "lifecycle": "failed",
                            SSE_ERROR_DATA_KEY: _shared_error("SYSTEM_INTERNAL_ERROR", safe),
                        },
                    )
                    raise
                await emit(
                    SSE_TOOL_CALL_TYPE,
                    {
                        "toolCallId": retrieval_call_id,
                        "toolName": "knowledge_retrieval",
                        "lifecycle": "completed",
                        "output": {
                            "summary": (
                                "SOP 检索完成"
                                if result.results
                                else "SOP 检索完成，未找到匹配引用"
                            )
                        },
                    },
                )
                if not result.results:
                    await emit(
                        SSE_TASK_STATUS_TYPE,
                        {
                            "taskId": task_id,
                            "status": "running",
                            "message": "未检索到匹配 SOP，将仅依据其他真实证据继续",
                            "progress": 15,
                        },
                    )
                for citation in result.results:
                    raw = citation.model_dump(mode="json", by_alias=True)
                    record = await self._store.call(
                        "add_evidence",
                        owner,
                        task_id,
                        knowledge_evidence(raw, tool_call_id=retrieval_call_id),
                    )
                    await emit(
                        SSE_REFERENCE_SOURCE_TYPE,
                        {"source": _evidence_reference(record)},
                    )
            knowledge_tool = create_knowledge_retrieval_tool(current_user, self._knowledge)
            tools[knowledge_tool.name] = knowledge_tool
            discovered = await self._tool_resolver.discover(
                owner, builtin_tool_names=frozenset(tools)
            )
            aiops_registry = build_aiops_tool_registry(discovered)
            tools.update(aiops_registry.tools)
            knowledge_descriptor = describe_builtin_knowledge_tool(knowledge_tool)
            tool_descriptors.clear()
            tool_descriptors.update(
                (item.name, item) for item in (knowledge_descriptor, *aiops_registry.catalog)
            )
            if find_search_log_tool(tuple(tools)) is None:
                raise AppError("SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE")
            if not task.current_plan:
                evidence = await self._store.call("list_evidence", owner, task_id)
                plan = await create_validated_plan(
                    self._model,
                    context=_model_context(task.alerts, evidence),
                    tool_catalog=(
                        knowledge_descriptor,
                        *aiops_registry.catalog,
                    ),
                    query_is_trusted=task.query is None,
                )
                task = await self._store.call("save_plan", owner, task_id, plan, replan_count=0)
                if task is None:
                    raise ValueError("诊断任务不可见")
            steps = await self._store.call("list_steps", owner, task_id)
            latest = await self._store.call("latest_checkpoint", owner, task_id)
            succeeded = {
                item.position
                for item in steps
                if item.plan_version == task.plan_version and item.status == "succeeded"
            }
            restored_position = len(succeeded)
            if latest is not None:
                candidate = latest.state.get("nextPosition")
                checkpoint_plan_version = latest.state.get("planVersion")
                if (
                    checkpoint_plan_version == task.plan_version
                    and isinstance(candidate, int)
                    and not isinstance(candidate, bool)
                ):
                    restored_position = max(restored_position, candidate)
            state = {**state, "next_position": restored_position, "route": "executor"}
            await checkpoint("planner", state)
            return state

        async def executor(state: DiagnosticState) -> DiagnosticState:
            await context.raise_if_cancelled()
            task = await self._store.call("get_task", owner, task_id)
            if task is None or state["next_position"] >= len(task.current_plan):
                state = {**state, "route": SSE_REPORT_TYPE}
                await checkpoint("executor", state)
                return state
            plan_step = task.current_plan[state["next_position"]]
            tool = tools.get(plan_step.tool_name)
            if tool is None:
                raise ValueError(f"计划工具在恢复后不可用: {plan_step.tool_name}")
            candidate_arguments = dict(plan_step.arguments)
            evidence = await self._store.call("list_evidence", owner, task_id)
            existing_steps = await self._store.call("list_steps", owner, task_id)
            matching_attempts = [
                item
                for item in existing_steps
                if item.plan_version == task.plan_version
                and item.position == plan_step.position
            ]
            search_query_override: str | None = None
            for interrupted in matching_attempts:
                if interrupted.status == "running":
                    await self._store.call(
                        "finish_step",
                        owner,
                        interrupted.id,
                        "failed",
                        error_message="provider_unavailable: interrupted attempt",
                        error_category="provider_unavailable",
                    )
            first_attempt = max((item.attempt for item in matching_attempts), default=0) + 1
            if first_attempt > 3:
                state = {**state, "last_error": "工具步骤已达到三次尝试上限"}
                await checkpoint("executor", state)
                return state
            for attempt in range(first_attempt, 4):
                await context.raise_if_cancelled()
                invocation_arguments = candidate_arguments
                phase = "input"
                step = None
                call_id = uuid4().hex
                try:
                    evidence = await self._store.call("list_evidence", owner, task_id)
                    try:
                        ensure_core_tool_schema_compatible(
                            plan_step.tool_name, _tool_schema(tool)
                        )
                    except ValueError as error:
                        raise ToolSchemaIncompatibleError(
                            f"{plan_step.tool_name} runtime Schema 与本地 adapter 不兼容"
                        ) from error
                    if is_query_builder_tool(plan_step.tool_name):
                        if self._search_log_defaults is None:
                            raise ToolConfigurationError("CLS 本地权威配置缺失")
                        invocation_arguments = cast(
                            dict[str, JsonValue],
                            build_text_to_search_log_query_input(
                                candidate_arguments,
                                self._search_log_defaults,
                                fallback_prompt=_diagnostic_query(task.query, task.alerts),
                            ).model_dump(mode="json", by_alias=True),
                        )
                    elif is_search_log_tool(plan_step.tool_name):
                        if self._search_log_defaults is None:
                            raise ToolConfigurationError("CLS 本地权威配置缺失")
                        proposed = dict(candidate_arguments)
                        query_artifact = _latest_query_artifact(evidence)
                        if search_query_override is not None:
                            proposed["Query"] = search_query_override
                        elif query_artifact is not None:
                            proposed["Query"] = query_artifact
                        invocation_arguments = normalize_search_log_arguments(
                            proposed,
                            schema=_tool_schema(tool),
                            defaults=self._search_log_defaults,
                            now_ms=self._now_ms,
                            fallback_query=_search_log_fallback_query(task.alerts),
                        )
                        invocation_arguments = cast(
                            dict[str, JsonValue],
                            SearchLogInput.model_validate(invocation_arguments).model_dump(
                                mode="json", by_alias=True, exclude_unset=True
                            ),
                        )
                    elif is_log_context_tool(plan_step.tool_name):
                        if self._search_log_defaults is None:
                            raise ToolConfigurationError("CLS 本地权威配置缺失")
                        hit = _latest_log_hit(evidence)
                        if hit is None:
                            raise ValueError("DescribeLogContext 缺少已验证 SearchLog 定位命中")
                        invocation_arguments = cast(
                            dict[str, JsonValue],
                            build_describe_log_context_input(
                                hit,
                                self._search_log_defaults,
                                proposed=candidate_arguments,
                            ).model_dump(mode="json", by_alias=True),
                        )
                    invocation_arguments = validate_runtime_tool_input(
                        tool, invocation_arguments
                    )
                    attempt_step = PlanStep(
                        plan_step.position,
                        plan_step.tool_name,
                        plan_step.purpose,
                        invocation_arguments,
                    )
                    step = await self._store.call(
                        "start_step",
                        owner,
                        task_id,
                        task.plan_version,
                        attempt_step,
                        attempt=attempt,
                    )
                    await emit(
                        SSE_TOOL_CALL_TYPE,
                        {
                            "toolCallId": call_id,
                            "toolName": plan_step.tool_name,
                            "lifecycle": "started",
                            "input": {
                                "argumentKeys": sorted(invocation_arguments),
                                "attempt": attempt,
                            },
                        },
                    )

                    phase = "invoke"
                    normalized = await self._auditor.execute(
                        current_user,
                        chat_session_id=None,
                        diagnostic_task_id=task_id,
                        tool_call_id=call_id,
                        tool_name=plan_step.tool_name,
                        arguments=invocation_arguments,
                        operation=_tool_and_adapter_operation(
                            tool,
                            invocation_arguments,
                            tool_name=plan_step.tool_name,
                            step_id=step.id,
                            tool_call_id=call_id,
                        ),
                    )
                    for item in normalized:
                        record = await self._store.call("add_evidence", owner, task_id, item)
                        await emit(
                            SSE_REFERENCE_SOURCE_TYPE, {"source": _evidence_reference(record)}
                        )
                    await self._store.call(
                        "finish_step",
                        owner,
                        step.id,
                        "succeeded",
                        result_summary="真实工具调用成功",
                    )
                    await emit(
                        SSE_TOOL_CALL_TYPE,
                        {
                            "toolCallId": call_id,
                            "toolName": plan_step.tool_name,
                            "lifecycle": "completed",
                            "output": {"summary": "真实工具调用成功", "attempt": attempt},
                        },
                    )
                    state = {
                        **state,
                        "next_position": state["next_position"] + 1,
                        "last_error": None,
                    }
                    break
                except Exception as error:
                    failure = classify_tool_failure(
                        error, phase=phase, attempt=attempt, arguments=invocation_arguments
                    )
                    if step is None:
                        failed_step = PlanStep(
                            plan_step.position,
                            plan_step.tool_name,
                            plan_step.purpose,
                            candidate_arguments,
                        )
                        step = await self._store.call(
                            "start_step",
                            owner,
                            task_id,
                            task.plan_version,
                            failed_step,
                            attempt=attempt,
                        )
                        await self._auditor.record_failed_attempt(
                            current_user,
                            diagnostic_task_id=task_id,
                            tool_call_id=call_id,
                            tool_name=plan_step.tool_name,
                            arguments=candidate_arguments,
                            error_message=failure.safe_message,
                        )
                    await self._store.call(
                        "finish_step",
                        owner,
                        step.id,
                        "failed",
                        error_message=failure.safe_message,
                        error_category=failure.category,
                    )
                    await emit(
                        SSE_TOOL_CALL_TYPE,
                        {
                            "toolCallId": call_id,
                            "toolName": plan_step.tool_name,
                            "lifecycle": "failed",
                            "output": {
                                "summary": failure.safe_message,
                                "attempt": attempt,
                                "errorCategory": failure.category,
                            },
                            SSE_ERROR_DATA_KEY: _shared_error(
                                "SYSTEM_INTERNAL_ERROR", failure.safe_message
                            ),
                        },
                    )
                    state = {**state, "last_error": failure.safe_message}
                    await checkpoint("executor", state)
                    if (
                        failure.category == "empty_result"
                        and is_search_log_tool(plan_step.tool_name)
                        and attempt < 3
                    ):
                        fallback_query = _search_log_fallback_query(task.alerts)
                        if (
                            fallback_query != "*"
                            and invocation_arguments.get("Query") != fallback_query
                        ):
                            search_query_override = fallback_query
                            continue
                    if failure.route == "permanent_failure":
                        raise RuntimeError(failure.safe_message) from error
                    if failure.route == "replan" or attempt == 3:
                        break
                    if failure.category == "input_validation":
                        descriptor = tool_descriptors.get(plan_step.tool_name)
                        if descriptor is None:
                            raise RuntimeError("工具能力描述在恢复时不可用") from error
                        repaired = await self._model.repair_tool_arguments(
                            context=_model_context(task.alerts, evidence),
                            tool=descriptor,
                            argument_keys=tuple(sorted(candidate_arguments)),
                            validation_errors=(failure.safe_message,),
                        )
                        candidate_arguments = repaired.arguments
                    if failure.delay:
                        await asyncio.sleep(failure.delay)
            await checkpoint("executor", state)
            return state

        async def replanner(state: DiagnosticState) -> DiagnosticState:
            await context.raise_if_cancelled()
            task = await self._store.call("get_task", owner, task_id)
            evidence = await self._store.call("list_evidence", owner, task_id)
            steps = await self._store.call("list_steps", owner, task_id)
            if task is None:
                raise ValueError("诊断任务不存在")
            if state["next_position"] >= len(task.current_plan):
                state = {**state, "route": SSE_REPORT_TYPE}
            else:
                remaining = task.current_plan[state["next_position"] :]
                decision = await self._model.replan(
                    context=_model_context(
                        task.alerts, evidence, plan=task.current_plan, steps=steps
                    ),
                    remaining_steps=remaining,
                )
                if decision.action == SSE_REPORT_TYPE:
                    state = {**state, "route": SSE_REPORT_TYPE}
                elif decision.action == "replan":
                    if task.replan_count >= MAX_REPLANS:
                        if any(item.kind != "alert" for item in evidence):
                            state = {**state, "route": SSE_REPORT_TYPE}
                            await checkpoint("replanner", state)
                            return state
                        raise ValueError("诊断重规划次数已达到上限且没有可用证据")
                    plan = validate_plan(
                        PlanDraft(
                            steps=decision.steps,
                            requiresTemporalContext=decision.requires_temporal_context,
                        ),
                        tuple(tools),
                        query_is_trusted=task.query is None,
                    )
                    await self._store.call(
                        "save_plan", owner, task_id, plan, replan_count=task.replan_count + 1
                    )
                    state = {**state, "next_position": 0, "route": "executor"}
                else:
                    state = {
                        **state,
                        "route": SSE_REPORT_TYPE if state.get("last_error") else "executor",
                    }
            progress = min(85, 20 + state["next_position"] * 10)
            await emit(
                SSE_TASK_STATUS_TYPE,
                {
                    "taskId": task_id,
                    "status": "running",
                    "message": "已根据真实证据重规划" if task.replan_count else "正在执行诊断计划",
                    "progress": progress,
                },
            )
            await checkpoint("replanner", state)
            return state

        async def report(state: DiagnosticState) -> DiagnosticState:
            await context.raise_if_cancelled()
            task = await self._store.call("get_task", owner, task_id)
            evidence = await self._store.call("list_evidence", owner, task_id)
            steps = await self._store.call("list_steps", owner, task_id)
            if task is None:
                raise ValueError("诊断任务不存在")
            evaluation = evaluate_claim_evidence(
                evidence=tuple(evidence),
                steps=tuple(steps),
                requires_temporal_context=any(
                    is_log_context_tool(item.tool_name) for item in task.current_plan
                ),
            )
            mode = "model"
            uncertainty = False
            evidence_ids: tuple[str, ...] = ()
            try:
                draft = await self._model.report(
                    context=_model_context(
                        task.alerts, evidence, plan=task.current_plan, steps=steps
                    )
                )
                markdown, claims, uncertainty = validate_report(
                    draft, evidence, alert_count=len(task.alerts)
                )
                linked_ids = {
                    evidence_id for claim in claims for evidence_id in claim.evidence_ids
                }
                if not set(evaluation.supporting_evidence_ids) <= linked_ids:
                    uncertainty = True
            except Exception:
                markdown, evidence_ids = build_fallback_report(
                    list(task.alerts), evidence, steps
                )
                claims = ()
                mode = "fallback"
                uncertainty = True
            trust_state = evaluation.trust_state
            if mode == "fallback" and trust_state == "verified_evidence":
                trust_state = "insufficient_evidence"
            if uncertainty and trust_state == "verified_evidence":
                trust_state = "insufficient_evidence"
            saved = await self._store.call(
                "create_report", owner, task_id, markdown, mode, uncertainty, trust_state
            )
            if mode == "model":
                position = 0
                for claim in claims:
                    for evidence_id in dict.fromkeys(claim.evidence_ids):
                        await self._store.call(
                            "link_evidence",
                            owner,
                            task_id,
                            saved.id,
                            evidence_id,
                            claim.claim_key,
                            claim.section,
                            position,
                        )
                        position += 1
            else:
                for position, evidence_id in enumerate(evidence_ids):
                    await self._store.call(
                        "link_evidence",
                        owner,
                        task_id,
                        saved.id,
                        evidence_id,
                        f"fallback-claim-{position + 1}",
                        "结论",
                        position,
                    )
            await emit(SSE_REPORT_TYPE, {SSE_REPORT_TYPE: _report_payload(saved)})
            if trust_state == "execution_failed":
                state = {**state, "route": "end"}
                await checkpoint(SSE_REPORT_TYPE, state)
                raise AppError("SYSTEM_UNAVAILABLE")
            await self._store.call("transition_task", owner, task_id, "succeeded")
            await emit(
                SSE_TASK_STATUS_TYPE,
                {"taskId": task_id, "status": "succeeded", "message": "诊断完成", "progress": 100},
            )
            state = {**state, "route": "end"}
            await checkpoint(SSE_REPORT_TYPE, state)
            return state

        graph: Any = StateGraph(DiagnosticState)
        graph.add_node("planner", planner)
        graph.add_node("executor", executor)
        graph.add_node("replanner", replanner)
        graph.add_node(SSE_REPORT_TYPE, report)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "executor")
        graph.add_edge("executor", "replanner")
        graph.add_conditional_edges(
            "replanner",
            _route_after_replanner,
            {"executor": "executor", SSE_REPORT_TYPE: SSE_REPORT_TYPE},
        )
        graph.add_edge(SSE_REPORT_TYPE, END)
        try:
            await graph.compile().ainvoke(
                DiagnosticState(
                    task_id=task_id,
                    next_position=0,
                    route="executor",
                    last_error=None,
                ),
                config={"recursion_limit": 2 * 8 + 8},
            )
        except BackgroundJobCancelledError:
            await self._store.call("transition_task", owner, task_id, "cancelled")
            await emit(
                SSE_TASK_STATUS_TYPE,
                {"taskId": task_id, "status": "cancelled", "message": "诊断已取消"},
            )
            raise
        except asyncio.CancelledError:
            if (
                context.termination_reason == "cancelled"
                or await context.cancellation_requested()
            ):
                await self._store.call("transition_task", owner, task_id, "cancelled")
                await emit(
                    SSE_TASK_STATUS_TYPE,
                    {"taskId": task_id, "status": "cancelled", "message": "诊断已取消"},
                )
            elif context.termination_reason == "timeout":
                await self._store.call(
                    "transition_task",
                    owner,
                    task_id,
                    "failed",
                    failure_code="SYSTEM_INTERNAL_ERROR",
                    failure_reason="诊断执行超时",
                )
                await emit(
                    SSE_ERROR_TYPE,
                    {SSE_ERROR_DATA_KEY: _shared_error("SYSTEM_INTERNAL_ERROR", "诊断执行超时")},
                )
            # worker shutdown 不等于用户取消；保留 running + checkpoint，等待 lease 恢复。
            raise
        except Exception as error:
            code = error.code if isinstance(error, AppError) else "SYSTEM_INTERNAL_ERROR"
            await self._store.call(
                "transition_task",
                owner,
                task_id,
                "failed",
                failure_code=code,
                failure_reason=self._safe_message(error),
            )
            await emit(
                SSE_ERROR_TYPE,
                {SSE_ERROR_DATA_KEY: _shared_error(code, self._safe_message(error))},
            )
            raise

    def _safe_message(self, error: Exception, sensitive: JsonValue | None = None) -> str:
        message = redact_error(str(error), dump_json(sensitive or {}))
        for secret in self._secret_values:
            message = message.replace(secret, "[redacted]")
        return message[:1000]


def _diagnostic_query(query: str | None, alerts: Sequence[dict[str, JsonValue]]) -> str:
    alert_names = ", ".join(str(item.get("alertName", "告警")) for item in alerts)
    return (query or f"请检索与这些活跃告警相关的处置 SOP：{alert_names}").strip()


def _latest_query_artifact(evidence: Sequence[DiagnosticEvidenceRecord]) -> str | None:
    for item in reversed(evidence):
        if item.kind != "query_artifact":
            continue
        query = item.metadata.get("Query", item.metadata.get("query"))
        if isinstance(query, str) and query.strip():
            return query.strip()
    return None


def _latest_log_hit(
    evidence: Sequence[DiagnosticEvidenceRecord],
) -> ClsSearchLogHit | None:
    for item in reversed(evidence):
        if item.kind != "log_hit":
            continue
        try:
            hit = ClsSearchLogHit.model_validate(item.metadata)
            if hit.has_context_locator:
                return hit
        except Exception:
            continue
    return None


def _tool_and_adapter_operation(
    tool: BaseTool,
    arguments: dict[str, JsonValue],
    *,
    tool_name: str,
    step_id: str,
    tool_call_id: str,
) -> Callable[[], Any]:
    async def invoke() -> tuple[NewEvidence, ...]:
        result = await tool.ainvoke(arguments)
        try:
            normalized = normalize_tool_evidence(
                tool_name=tool_name,
                result=result,
                step_id=step_id,
                tool_call_id=tool_call_id,
            )
        except Exception as error:
            raise ToolOutputValidationError(
                f"{tool_name} 输出未通过 adapter 校验"
            ) from error
        if not normalized:
            raise ToolEmptyResultError(f"{tool_name} 返回空结果")
        return normalized

    return invoke


def _current_time_ms() -> int:
    return int(utc_now().timestamp() * 1000)


def _tool_schema(tool: BaseTool) -> Mapping[str, object]:
    schema = tool.args_schema
    if isinstance(schema, dict):
        return cast(dict[str, object], schema)
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        model_schema = schema.model_json_schema()
        return cast(dict[str, object], model_schema)
    raise ValueError(f"工具 {tool.name} 缺少可验证的 JSON Schema")


def _search_log_fallback_query(alerts: Sequence[dict[str, JsonValue]]) -> str:
    for alert in alerts:
        labels = alert.get("labels")
        if not isinstance(labels, dict):
            continue
        for key in ("incident_id", "trace_id", "alertname", "service"):
            value = labels.get(key)
            if isinstance(value, str) and value.strip():
                escaped = value.strip().replace("\\", "\\\\").replace('"', '\\"')
                return f'{key}:"{escaped}"'
    return "*"


def _model_context(
    alerts: Sequence[dict[str, JsonValue]],
    evidence: Sequence[DiagnosticEvidenceRecord],
    *,
    plan: Sequence[PlanStep] = (),
    steps: Sequence[DiagnosticStepRecord] = (),
) -> str:
    safe_steps = [
        {
            "toolName": item.tool_name,
            "status": item.status,
            "resultSummary": item.result_summary,
        }
        for item in steps
    ]
    sop_state = (
        "已获得 SOP 引用"
        if any(item.kind == "knowledge" for item in evidence)
        else "未检索到 SOP"
    )
    return (
        f"告警：{list(alerts)}\nSOP 状态：{sop_state}\n"
        f"最终计划：{list(plan)}\n步骤摘要：{safe_steps}"
        f"\n已持久化证据：\n{summarize_evidence(evidence)}"
    )


def _evidence_reference(record: DiagnosticEvidenceRecord) -> dict[str, object]:
    return {
        "evidenceId": record.id,
        "kind": record.kind,
        "source": record.source,
        "title": record.title,
        "excerpt": record.summary,
        "metadata": record.metadata,
    }


def _shared_error(code: ErrorCode, message: str) -> dict[str, object]:
    definition = ERROR_DEFINITIONS[code]
    return {
        "code": definition.code,
        "category": definition.category,
        "httpStatus": definition.http_status,
        "message": message or definition.default_message,
    }


def _report_payload(record: DiagnosticReportRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "diagnosticTaskId": record.diagnostic_task_id,
        "revision": record.revision,
        "markdown": record.markdown,
        "generationMode": record.generation_mode,
        "uncertainty": record.uncertainty,
        "trustState": record.trust_state,
        "createdAt": record.created_at.isoformat().replace("+00:00", "Z"),
    }
