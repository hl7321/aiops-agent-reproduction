"""AIOps 诊断 FastAPI dependencies。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.aiops.service import DiagnosticService
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
    SqliteAgentToolCallAuditRepository,
)
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.sqlite import get_session


def get_diagnostic_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DiagnosticService:
    return DiagnosticService(
        SqliteDiagnosticRepository(session),
        SqliteBackgroundJobStore(session),
        SqliteAgentToolCallAuditRepository(session),
    )
