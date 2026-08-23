from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest
from langchain_core.tools import BaseTool, tool

from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.aiops.cases.service import DiagnosisCasePersistor
from super_ai.aiops.models import PlanStep
from super_ai.aiops.planning import (
    PlanDraft,
    PlanStepDraft,
    ReplanDraft,
    ReportDraft,
    SearchLogQueryDefaults,
    ToolArgumentRepairDraft,
)
from super_ai.aiops.runtime import DiagnosticRuntime
from super_ai.aiops.tool_policy import ToolCapabilityDescriptor
from super_ai.api_contracts import KnowledgeRetrievalToolInput, KnowledgeRetrievalToolOutput
from super_ai.api_responses import AppError
from super_ai.background_jobs.handlers import BackgroundJobContext
from super_ai.background_jobs.models import BackgroundJobEventRecord, NewBackgroundJob
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
    SqliteAgentToolCallAuditRepository,
    SqliteAgentToolCallAuditStore,
)
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.diagnostic_repositories import (
    SqliteDiagnosticRepository,
    SqliteDiagnosticStore,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.project_config import JsonValue
from super_ai.tenancy.context import CurrentUser


class FakeKnowledge:
    def __init__(self, order: list[str]) -> None:
        self.order = order

    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput:
        assert current_user.owner_user_id and tool_input.query
        self.order.append("knowledge")
        return KnowledgeRetrievalToolOutput(results=[])


class FailingKnowledge(FakeKnowledge):
    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput:
        self.order.append("knowledge")
        raise RuntimeError("SOP 检索失败 sentinel-secret")


class FakeResolver:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.arguments: list[dict[str, object]] = []

    async def discover(
        self, owner_user_id: str, *, builtin_tool_names: frozenset[str]
    ) -> tuple[BaseTool, ...]:
        assert owner_user_id
        assert builtin_tool_names == frozenset({"knowledge_retrieval"})
        self.order.append("mcp")

        @tool("SearchLog")
        async def search_log(
            From: float,
            To: float,
            Query: str,
            Region: str,
            TopicId: str = "",
        ) -> object:
            """查询真实测试边界日志。"""
            self.arguments.append(
                {
                    "From": From,
                    "To": To,
                    "Query": Query,
                    "Region": Region,
                    "TopicId": TopicId,
                }
            )
            return {
                "structuredContent": [
                    {
                        "Time": int(To),
                        "PkgId": "pkg-test",
                        "PkgLogId": 1,
                        "LogJson": f'{{"message":"真实日志:{Query}","service":"checkout"}}',
                    }
                ]
            }

        return (search_log,)


class FakeModel:
    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft:
        assert "HighError" in context
        assert not validation_errors
        assert tuple(item.name for item in tool_catalog) == ("knowledge_retrieval", "SearchLog")
        return PlanDraft(
            steps=[
                PlanStepDraft(
                    toolName="SearchLog", purpose="查询告警日志", arguments={"query": "error"}
                )
            ]
        )

    async def repair_tool_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        argument_keys: Sequence[str],
        validation_errors: Sequence[str],
    ) -> ToolArgumentRepairDraft:
        raise AssertionError("有效测试参数不应进入纠错")

    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft:
        assert context and not remaining_steps
        return ReplanDraft(action="report", reason="已有真实证据")

    async def report(self, *, context: str) -> ReportDraft:
        assert context
        raise RuntimeError("模型报告失败以验证诚实 fallback")


class EmptyResolver:
    async def discover(
        self, owner_user_id: str, *, builtin_tool_names: frozenset[str]
    ) -> tuple[BaseTool, ...]:
        assert owner_user_id
        assert builtin_tool_names == frozenset({"knowledge_retrieval"})
        return ()


class ReportOnFailureModel(FakeModel):
    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft:
        assert context and remaining_steps
        return ReplanDraft(action="report", reason="尝试耗尽，生成诚实失败说明")


class RepairingModel(FakeModel):
    def __init__(self) -> None:
        self.validation_errors: tuple[str, ...] = ()

    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft:
        assert context and tool_catalog and not validation_errors
        return PlanDraft(
            steps=[
                PlanStepDraft(
                    toolName="SearchLog", purpose="查询告警日志", arguments={"Query": ""}
                )
            ]
        )

    async def repair_tool_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        argument_keys: Sequence[str],
        validation_errors: Sequence[str],
    ) -> ToolArgumentRepairDraft:
        assert context and tool.name == "SearchLog" and "Query" in argument_keys
        self.validation_errors = tuple(validation_errors)
        return ToolArgumentRepairDraft(arguments={"Query": "error"})


class NeverCalledModel(FakeModel):
    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft:
        raise AssertionError("无 SearchLog 时不得调用 planner model")


async def test_graph_runtime_persists_tool_evidence_checkpoint_and_fallback(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'runtime.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            diagnostics = SqliteDiagnosticRepository(session)
            task = await diagnostics.create_task("owner", None, [{"alertName": "HighError"}])
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner",
                NewBackgroundJob(
                    kind="aiops_diagnosis",
                    resource_type="diagnostic_task",
                    resource_id=task.id,
                    payload={"taskId": task.id},
                ),
            )
        order: list[str] = []
        resolver = FakeResolver(order)
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge(order),
            resolver,
            FakeModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        assert order == ["knowledge", "mcp"]
        assert resolver.arguments == [
            {
                "From": 1_787_476_500_000,
                "To": 1_787_480_100_000,
                "Query": "error",
                "Region": "ap-guangzhou",
                "TopicId": "topic-real",
            }
        ]
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteDiagnosticRepository(session)
            saved = await repository.get_task("owner", task.id)
            evidence = await repository.list_evidence("owner", task.id)
            report = await repository.latest_report("owner", task.id)
            links = await repository.list_links("owner", task.id)
            checkpoint = await repository.latest_checkpoint("owner", task.id)
            events = await SqliteBackgroundJobStore(session).list_events(
                "owner", job.id, after_sequence=0
            )
            cases = await DiagnosisCasePersistor(runtime.session_factory).list("owner")
        assert saved is not None and saved.status == "succeeded"
        assert [item.kind for item in evidence] == ["log_hit"]
        assert report is not None and report.generation_mode == "fallback"
        assert report.uncertainty is True and "证据不足" in report.markdown
        assert report.trust_state == "insufficient_evidence"
        assert [item.evidence_id for item in links] == [evidence[0].id]
        assert checkpoint is not None and checkpoint.node == "report"
        assert events is not None
        assert cases == []
        assert any("未检索到匹配 SOP" in str(item.data) for item in events)
    finally:
        await runtime.close()


async def test_executor_repairs_pydantic_input_and_audits_both_attempts(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'repair-input.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner", None, [{"alertName": "HighError"}])
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner", NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id})
            )
        model = RepairingModel()
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge([]),
            FakeResolver([]),
            model,
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteDiagnosticRepository(session)
            steps = await repository.list_steps("owner", task.id)
            audits = await SqliteAgentToolCallAuditRepository(session).list_for_diagnostic(
                "owner", task.id
            )

        assert [(item.attempt, item.status, item.error_category) for item in steps] == [
            (1, "failed", "input_validation"),
            (2, "succeeded", None),
        ]
        assert [item.status for item in audits if item.tool_name == "SearchLog"] == [
            "failed",
            "completed",
        ]
        assert model.validation_errors and "Query" in model.validation_errors[0]
        assert "input_value" not in model.validation_errors[0]
    finally:
        await runtime.close()


async def test_missing_search_log_fails_before_planner_model(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'missing-tool.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner", None, [{"alertName": "HighError"}])
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner",
                NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id}),
            )
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge([]),
            EmptyResolver(),
            NeverCalledModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        with pytest.raises(AppError) as caught:
            await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        assert caught.value.code == "SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE"
        async with transaction_scope(runtime.session_factory) as session:
            saved = await SqliteDiagnosticRepository(session).get_task("owner", task.id)
        assert saved is not None
        assert saved.status == "failed"
        assert saved.failure_code == "SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE"
    finally:
        await runtime.close()


async def test_sop_failure_emits_failed_tool_event_and_redacts_secret(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'sop-failure.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            task = await SqliteDiagnosticRepository(session).create_task(
                "owner", None, [{"alertName": "HighError"}]
            )
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner", NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id})
            )
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FailingKnowledge([]),
            EmptyResolver(),
            NeverCalledModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            secret_values=("sentinel-secret",),
        )

        async def not_cancelled() -> bool:
            return False

        with pytest.raises(RuntimeError, match="sentinel-secret"):
            await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        async with transaction_scope(runtime.session_factory) as session:
            events = await SqliteBackgroundJobStore(session).list_events(
                "owner", job.id, after_sequence=0
            )
            saved = await SqliteDiagnosticRepository(session).get_task("owner", task.id)
        assert events is not None
        failed_events: list[BackgroundJobEventRecord] = []
        for item in events:
            event_data = cast(dict[str, JsonValue], item.data)
            semantic_data = event_data.get("data")
            if (
                item.type == "progress"
                and event_data.get("eventType") == "tool.call"
                and isinstance(semantic_data, dict)
                and semantic_data.get("lifecycle") == "failed"
            ):
                failed_events.append(item)
        assert len(failed_events) == 1
        assert "sentinel-secret" not in str(failed_events[0].data)
        assert saved is not None and saved.status == "failed"
        assert saved.failure_reason is not None
        assert "sentinel-secret" not in saved.failure_reason
    finally:
        await runtime.close()


async def test_restore_ignores_checkpoint_from_previous_plan_version(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'checkpoint-version.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner", None, [{"alertName": "HighError"}])
            task = await repository.save_plan(
                "owner",
                task.id,
                (PlanStep(0, "SearchLog", "查询真实日志", {"query": "error"}),),
                replan_count=0,
            )
            assert task is not None and task.plan_version == 1
            await repository.save_checkpoint(
                "owner",
                task.id,
                "replanner",
                {"planVersion": 0, "nextPosition": 8, "route": "executor"},
            )
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner", NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id})
            )
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge([]),
            FakeResolver([]),
            FakeModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        async with transaction_scope(runtime.session_factory) as session:
            steps = await SqliteDiagnosticRepository(session).list_steps("owner", task.id)
        assert [(step.plan_version, step.position, step.status) for step in steps] == [
            (1, 0, "succeeded")
        ]
    finally:
        await runtime.close()


async def test_restore_continues_attempt_sequence_without_reusing_attempt_one(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'attempt-recovery.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner", None, [{"alertName": "HighError"}])
            task = await repository.save_plan(
                "owner",
                task.id,
                (PlanStep(0, "SearchLog", "查询真实日志", {"query": "error"}),),
                replan_count=0,
            )
            assert task is not None
            first = await repository.start_step(
                "owner", task.id, task.plan_version, task.current_plan[0], attempt=1
            )
            await repository.finish_step(
                "owner",
                first.id,
                "failed",
                error_message="timeout: TimeoutError",
                error_category="timeout",
            )
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner", NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id})
            )
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge([]),
            FakeResolver([]),
            FakeModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        async with transaction_scope(runtime.session_factory) as session:
            steps = await SqliteDiagnosticRepository(session).list_steps("owner", task.id)

        assert [(step.attempt, step.status) for step in steps] == [
            (1, "failed"),
            (2, "succeeded"),
        ]
    finally:
        await runtime.close()


async def test_exhausted_required_search_attempts_persist_failed_explanation(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'attempts-exhausted.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add(
                UserModel(
                    id="owner",
                    email="owner@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner", None, [{"alertName": "HighError"}])
            task = await repository.save_plan(
                "owner",
                task.id,
                (PlanStep(0, "SearchLog", "查询真实日志", {"query": "error"}),),
                replan_count=0,
            )
            assert task is not None
            for attempt in range(1, 4):
                step = await repository.start_step(
                    "owner", task.id, task.plan_version, task.current_plan[0], attempt=attempt
                )
                await repository.finish_step(
                    "owner",
                    step.id,
                    "failed",
                    error_message="timeout: TimeoutError",
                    error_category="timeout",
                )
            job = await SqliteBackgroundJobStore(session).enqueue(
                "owner", NewBackgroundJob(kind="aiops_diagnosis", payload={"taskId": task.id})
            )
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge([]),
            FakeResolver([]),
            ReportOnFailureModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            search_log_defaults=SearchLogQueryDefaults("ap-guangzhou", "topic-real"),
            now_ms=lambda: 1_787_480_100_000,
        )

        async def not_cancelled() -> bool:
            return False

        with pytest.raises(AppError) as caught:
            await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        assert caught.value.code == "SYSTEM_UNAVAILABLE"
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteDiagnosticRepository(session)
            saved = await repository.get_task("owner", task.id)
            report = await repository.latest_report("owner", task.id)

        assert saved is not None and saved.status == "failed"
        assert report is not None and report.trust_state == "execution_failed"
        assert report.uncertainty is True
    finally:
        await runtime.close()
