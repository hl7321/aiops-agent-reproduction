from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest
from langchain_core.tools import BaseTool, tool

from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.aiops.cases.service import DiagnosisCasePersistor
from super_ai.aiops.models import PlanStep
from super_ai.aiops.planning import PlanDraft, PlanStepDraft, ReplanDraft, ReportDraft
from super_ai.aiops.runtime import DiagnosticRuntime
from super_ai.api_contracts import KnowledgeRetrievalToolInput, KnowledgeRetrievalToolOutput
from super_ai.api_responses import AppError
from super_ai.background_jobs.handlers import BackgroundJobContext
from super_ai.background_jobs.models import BackgroundJobEventRecord, NewBackgroundJob
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
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

    async def discover(
        self, owner_user_id: str, *, builtin_tool_names: frozenset[str]
    ) -> tuple[BaseTool, ...]:
        assert owner_user_id
        assert builtin_tool_names == frozenset({"knowledge_retrieval"})
        self.order.append("mcp")

        @tool("SearchLog")
        async def search_log(query: str) -> dict[str, str]:
            """查询真实测试边界日志。"""
            return {"message": f"真实日志:{query}", "service": "checkout"}

        return (search_log,)


class FakeModel:
    async def plan(self, *, context: str, tool_names: Sequence[str]) -> PlanDraft:
        assert "HighError" in context
        assert tuple(tool_names) == ("knowledge_retrieval", "SearchLog")
        return PlanDraft(
            steps=[
                PlanStepDraft(
                    toolName="SearchLog", purpose="查询告警日志", arguments={"query": "error"}
                )
            ]
        )

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


class NeverCalledModel(FakeModel):
    async def plan(self, *, context: str, tool_names: Sequence[str]) -> PlanDraft:
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
            task = await diagnostics.create_task("owner", "排查", [{"alertName": "HighError"}])
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
        diagnosis = DiagnosticRuntime(
            SqliteDiagnosticStore(runtime.session_factory),
            FakeKnowledge(order),
            FakeResolver(order),
            FakeModel(),
            AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory), now=utc_now
            ),
            case_persistor=DiagnosisCasePersistor(runtime.session_factory),
        )

        async def not_cancelled() -> bool:
            return False

        await diagnosis.run(BackgroundJobContext(job.id, "owner", not_cancelled), task.id)
        assert order == ["knowledge", "mcp"]
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
        assert [item.kind for item in evidence] == ["log"]
        assert report is not None and report.generation_mode == "fallback"
        assert report.uncertainty is True and "证据不足" in report.markdown
        assert [item.evidence_id for item in links] == [evidence[0].id]
        assert checkpoint is not None and checkpoint.node == "report"
        assert events is not None
        assert len(cases) == 1 and cases[0].task_id == task.id
        assert cases[0].evidence_ids == (evidence[0].id,)
        assert any("未检索到匹配 SOP" in str(item.data) for item in events)
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
