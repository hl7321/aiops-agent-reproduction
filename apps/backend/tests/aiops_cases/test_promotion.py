import asyncio
from pathlib import Path

import pytest
from sqlalchemy import func, select

from super_ai.aiops.cases.service import DiagnosisCasePromoter
from super_ai.aiops.models import NewEvidence
from super_ai.api_responses import AppError
from super_ai.auth.models import UserRecord
from super_ai.feedback.models import FeedbackUpsert
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_repositories import SqliteUserRepository
from super_ai.memory.extended_sqlite.background_job_models import BackgroundJobModel
from super_ai.memory.extended_sqlite.diagnosis_case_models import (
    DiagnosisCaseModel,
    DiagnosticCaseSourceModel,
)
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.extended_sqlite.feedback_repositories import SqliteFeedbackRepository
from super_ai.memory.extended_sqlite.knowledge_models import KnowledgeDocumentModel
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def _runtime(path: Path) -> PersistenceRuntime:
    url = f"sqlite+aiosqlite:///{path}"
    await upgrade_database(url)
    return PersistenceRuntime.start(DatabaseSettings(url=url))


async def _report(
    runtime: PersistenceRuntime,
    owner: str,
    *,
    trust_state: str = "verified_evidence",
    uncertainty: bool = False,
    feedback: str | None = "positive",
    root_cause: str = "连接池耗尽",
    remediation: str = "扩容并检查泄漏",
    summary: str = "真实日志已确认",
    dependency: str = "mysql",
) -> tuple[str, str, str | None]:
    async with transaction_scope(runtime.session_factory) as session:
        users = SqliteUserRepository(session)
        if await users.get_by_email(f"{owner}@example.com") is None:
            await users.add(
                UserRecord(id=owner, email=f"{owner}@example.com", password_hash="safe-hash")
            )
        diagnostics = SqliteDiagnosticRepository(session)
        task = await diagnostics.create_task(
            owner,
            None,
            [{"alertName": "HighError", "service": "checkout", "dependency": dependency}],
        )
        evidence = await diagnostics.add_evidence(
            owner,
            task.id,
            NewEvidence(
                "log_hit",
                "SearchLog",
                "真实错误日志",
                "连接池等待超时",
                "连接池等待超时",
                {"Time": 1, "PkgId": "pkg", "PkgLogId": 1, "LogJson": "timeout"},
            ),
        )
        report = await diagnostics.create_report(
            owner,
            task.id,
            (
                f"# 告警分析报告\n- 根因结论：{root_cause}\n- 建议：{remediation}\n"
                f"- 整体评估：{summary}"
            ),
            "model",
            uncertainty,
            trust_state,  # type: ignore[arg-type]
        )
        await diagnostics.link_evidence(
            owner, task.id, report.id, evidence.id, "root-cause", "根因", 0
        )
        await diagnostics.transition_task(owner, task.id, "succeeded")
        feedback_id = None
        if feedback is not None:
            saved = await SqliteFeedbackRepository(session).upsert(
                owner,
                FeedbackUpsert(
                    "diagnostic_report", report.id, "", feedback, None, None, None  # type: ignore[arg-type]
                ),
            )
            feedback_id = saved.id
        return task.id, report.id, feedback_id


async def _asset_counts(runtime: PersistenceRuntime) -> tuple[int, int, int]:
    async with transaction_scope(runtime.session_factory) as session:
        cases = await session.scalar(select(func.count()).select_from(DiagnosisCaseModel))
        documents = await session.scalar(select(func.count()).select_from(KnowledgeDocumentModel))
        jobs = await session.scalar(select(func.count()).select_from(BackgroundJobModel))
    return int(cases or 0), int(documents or 0), int(jobs or 0)


async def test_verified_positive_report_requires_explicit_promotion(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "positive.sqlite3")
    try:
        task_id, _report_id, _feedback_id = await _report(runtime, "owner")
        assert await _asset_counts(runtime) == (0, 0, 0)
        result = await DiagnosisCasePromoter(runtime.session_factory).promote(
            "owner", task_id
        )
        assert result.status == "created"
        assert result.item is not None and result.item.promotion_status == "canonical"
        async with transaction_scope(runtime.session_factory) as session:
            document = await session.get(KnowledgeDocumentModel, result.item.document_id)
        assert document is not None
        assert document.source_metadata["incidentFingerprint"] == result.item.incident_fingerprint
        assert (
            document.source_metadata["knowledgeFingerprint"]
            == result.item.knowledge_fingerprint
        )
        assert document.source_metadata["fingerprintVersion"] == "v1"
        assert await _asset_counts(runtime) == (1, 1, 1)
    finally:
        await runtime.close()


@pytest.mark.parametrize(
    ("trust_state", "uncertainty", "feedback"),
    [
        ("verified_evidence", False, None),
        ("verified_evidence", False, "negative"),
        ("verified_evidence", True, "positive"),
        ("insufficient_evidence", True, "positive"),
        ("execution_failed", True, "positive"),
    ],
)
async def test_unapproved_or_untrusted_report_has_zero_side_effects(
    tmp_path: Path, trust_state: str, uncertainty: bool, feedback: str | None
) -> None:
    runtime = await _runtime(tmp_path / f"blocked-{trust_state}-{feedback}.sqlite3")
    try:
        task_id, _report_id, _ = await _report(
            runtime,
            "owner",
            trust_state=trust_state,
            uncertainty=uncertainty,
            feedback=feedback,
        )
        with pytest.raises(AppError) as caught:
            await DiagnosisCasePromoter(runtime.session_factory).promote(
                "owner", task_id, resolution="create_new"
            )
        assert caught.value.code == "BUSINESS_RULE_VIOLATION"
        assert await _asset_counts(runtime) == (0, 0, 0)
    finally:
        await runtime.close()


async def test_deleted_feedback_and_cross_owner_cannot_be_forged(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "deleted.sqlite3")
    try:
        task_id, _report_id, feedback_id = await _report(runtime, "owner")
        assert feedback_id is not None
        async with transaction_scope(runtime.session_factory) as session:
            assert await SqliteFeedbackRepository(session).delete("owner", feedback_id)
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        for attempted_owner in ("owner", "other-owner"):
            with pytest.raises(AppError):
                await promoter.promote(attempted_owner, task_id, resolution="create_new")
        assert await _asset_counts(runtime) == (0, 0, 0)
    finally:
        await runtime.close()


async def test_same_report_and_cross_task_exact_duplicate_are_canonical(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "exact.sqlite3")
    try:
        first_task, _first_report, _ = await _report(runtime, "owner")
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        first = await promoter.promote("owner", first_task)
        repeated = await promoter.promote("owner", first_task)
        assert first.item is not None and repeated.item is not None
        assert repeated.status == "existing" and repeated.item.id == first.item.id

        second_task, _second_report, _ = await _report(runtime, "owner")
        duplicate = await promoter.promote("owner", second_task)
        assert duplicate.status == "existing"
        assert duplicate.item is not None and duplicate.item.id == first.item.id
        async with transaction_scope(runtime.session_factory) as session:
            sources = await session.scalar(
                select(func.count()).select_from(DiagnosticCaseSourceModel)
            )
        assert await _asset_counts(runtime) == (1, 1, 1)
        assert sources == 2
    finally:
        await runtime.close()


async def test_semantic_similar_requires_explicit_merge_or_create_new(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "similar.sqlite3")
    try:
        first_task, _report_id, _ = await _report(runtime, "owner")
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        first = await promoter.promote("owner", first_task)
        assert first.item is not None
        second_task, _second_report, _ = await _report(
            runtime,
            "owner",
            root_cause="连接池接近耗尽并发生等待",
            remediation="扩容连接池并检查连接泄漏",
        )
        pending = await promoter.promote("owner", second_task)
        assert pending.status == "needs_review" and pending.item is None
        assert pending.candidates and pending.candidates[0].item.id == first.item.id
        assert await _asset_counts(runtime) == (1, 1, 1)

        merged = await promoter.promote(
            "owner",
            second_task,
            resolution="merge",
            candidate_case_id=first.item.id,
        )
        assert merged.status == "merged" and merged.item is not None
        assert merged.item.id == first.item.id
        assert await _asset_counts(runtime) == (1, 1, 1)
    finally:
        await runtime.close()


async def test_concurrent_promotion_creates_one_canonical_asset_set(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "concurrent-promotion.sqlite3")
    try:
        task_id, _report_id, _ = await _report(runtime, "owner")
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        results = await asyncio.gather(
            promoter.promote("owner", task_id),
            promoter.promote("owner", task_id),
        )
        assert results[0].item is not None and results[1].item is not None
        assert results[0].item.id == results[1].item.id
        assert await _asset_counts(runtime) == (1, 1, 1)
    finally:
        await runtime.close()


@pytest.mark.parametrize(
    ("second_overrides", "matched_fingerprint"),
    [
        ({"summary": "同一故障的补充说明"}, "incident"),
        ({"dependency": "mysql-primary"}, "knowledge"),
    ],
)
async def test_either_exact_fingerprint_reuses_canonical_case(
    tmp_path: Path, second_overrides: dict[str, str], matched_fingerprint: str
) -> None:
    runtime = await _runtime(tmp_path / f"exact-{matched_fingerprint}.sqlite3")
    try:
        first_task, _report_id, _ = await _report(runtime, "owner")
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        first = await promoter.promote("owner", first_task)
        if matched_fingerprint == "incident":
            second_task, _second_report, _ = await _report(
                runtime, "owner", summary=second_overrides["summary"]
            )
        else:
            second_task, _second_report, _ = await _report(
                runtime, "owner", dependency=second_overrides["dependency"]
            )
        duplicate = await promoter.promote("owner", second_task)

        assert first.item is not None and duplicate.item is not None
        assert duplicate.status == "existing"
        assert duplicate.item.id == first.item.id
        assert await _asset_counts(runtime) == (1, 1, 1)
    finally:
        await runtime.close()


async def test_feedback_can_be_deleted_after_promotion_without_deleting_assets(
    tmp_path: Path,
) -> None:
    runtime = await _runtime(tmp_path / "feedback-after-promotion.sqlite3")
    try:
        task_id, _report_id, feedback_id = await _report(runtime, "owner")
        assert feedback_id is not None
        promoter = DiagnosisCasePromoter(runtime.session_factory)
        created = await promoter.promote("owner", task_id)
        assert created.item is not None

        async with transaction_scope(runtime.session_factory) as session:
            assert await SqliteFeedbackRepository(session).delete("owner", feedback_id)

        assert await _asset_counts(runtime) == (1, 1, 1)
        with pytest.raises(AppError):
            await promoter.promote("owner", task_id)
        assert await _asset_counts(runtime) == (1, 1, 1)
    finally:
        await runtime.close()
