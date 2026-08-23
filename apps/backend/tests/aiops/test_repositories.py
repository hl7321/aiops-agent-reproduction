from pathlib import Path

import pytest

from super_ai.aiops.models import NewEvidence, PlanStep
from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def _runtime(tmp_path: Path) -> PersistenceRuntime:
    url = f"sqlite+aiosqlite:///{tmp_path / 'repo.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        for owner in ("user-a", "user-b"):
            session.add(
                UserModel(
                    id=owner,
                    email=f"{owner}@example.com",
                    password_hash="hash",
                    created_at=now,
                    updated_at=now,
                )
            )
    return runtime


async def test_repository_is_owner_scoped_and_links_same_task(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path)
    try:
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("user-a", "排查错误", [{"alertName": "HighError"}])
            assert await repository.get_task("user-b", task.id) is None
            planned = await repository.save_plan(
                "user-a",
                task.id,
                (PlanStep(0, "SearchLog", "查询日志", {"query": "error"}),),
                replan_count=0,
            )
            assert planned is not None and planned.plan_version == 1
            failed_attempt = await repository.start_step(
                "user-a", task.id, 1, planned.current_plan[0], attempt=1
            )
            await repository.finish_step(
                "user-a",
                failed_attempt.id,
                "failed",
                error_message="timeout: TimeoutException",
                error_category="timeout",
            )
            successful_attempt = await repository.start_step(
                "user-a", task.id, 1, planned.current_plan[0], attempt=2
            )
            await repository.finish_step(
                "user-a", successful_attempt.id, "succeeded", result_summary="真实调用成功"
            )
            attempts = await repository.list_steps("user-a", task.id)
            assert [(item.attempt, item.error_category) for item in attempts] == [
                (1, "timeout"),
                (2, None),
            ]
            first = await repository.save_checkpoint(
                "user-a", task.id, "planner", {"nextStepIndex": 0}
            )
            second = await repository.save_checkpoint(
                "user-a", task.id, "executor", {"nextStepIndex": 1}
            )
            assert (first.checkpoint_version, second.checkpoint_version) == (1, 2)
            evidence = await repository.add_evidence(
                "user-a",
                task.id,
                NewEvidence("log", "CLS", "日志", "真实日志", "service failed", {}),
            )
            with pytest.raises(ValueError, match="证据步骤必须属于"):
                await repository.add_evidence(
                    "user-a",
                    task.id,
                    NewEvidence(
                        "log",
                        "CLS",
                        "越权步骤",
                        "拒绝",
                        "拒绝",
                        {},
                        diagnostic_step_id="other-owner-step",
                    ),
                )
            with pytest.raises(ValueError, match="证据工具调用必须属于"):
                await repository.add_evidence(
                    "user-a",
                    task.id,
                    NewEvidence(
                        "log",
                        "CLS",
                        "越权审计",
                        "拒绝",
                        "拒绝",
                        {},
                        tool_call_id="other-owner-call",
                    ),
                )
            report = await repository.create_report(
                "user-a", task.id, "# 告警分析报告", "fallback", True
            )
            link = await repository.link_evidence(
                "user-a", task.id, report.id, evidence.id, "root-1", "根因", 0
            )
            assert link.evidence_id == evidence.id
            with pytest.raises(ValueError, match="同一 owner/task"):
                await repository.link_evidence(
                    "user-b", task.id, report.id, evidence.id, "bad", "bad", 0
                )
    finally:
        await runtime.close()


async def test_automatic_job_retry_maps_diagnostic_back_to_accepted(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path)
    try:
        async with transaction_scope(runtime.session_factory) as session:
            diagnostics = SqliteDiagnosticRepository(session)
            task = await diagnostics.create_task("user-a", None, [{"alertName": "HighError"}])
            jobs = SqliteBackgroundJobStore(session)
            job = await jobs.enqueue(
                "user-a",
                NewBackgroundJob(
                    kind="aiops_diagnosis",
                    resource_type="diagnostic_task",
                    resource_id=task.id,
                    payload={"taskId": task.id},
                    max_attempts=2,
                ),
            )
            claimed = await jobs.claim_next("worker", now=utc_now(), lease_seconds=30)
            assert claimed is not None and claimed.id == job.id
            await diagnostics.transition_task("user-a", task.id, "running")
            retrying = await jobs.fail_execution(
                job.id, "worker", now=utc_now(), error_message="真实工具暂时不可用"
            )
            refreshed = await diagnostics.get_task("user-a", task.id)
        assert retrying is not None and retrying.status == "queued"
        assert refreshed is not None and refreshed.status == "accepted"
    finally:
        await runtime.close()
