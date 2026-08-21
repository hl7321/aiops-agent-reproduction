"""owner-scoped 诊断 case Repository Protocol。"""

from typing import Protocol

from super_ai.aiops.cases.models import CaseMaterial, DiagnosisCaseRecord


class DiagnosisCaseRepository(Protocol):
    async def get_by_task(
        self, owner_user_id: str, task_id: str
    ) -> DiagnosisCaseRecord | None: ...

    async def get(self, owner_user_id: str, case_id: str) -> DiagnosisCaseRecord | None: ...

    async def list(self, owner_user_id: str) -> list[DiagnosisCaseRecord]: ...

    async def create(
        self,
        owner_user_id: str,
        task_id: str,
        report_id: str,
        document_id: str,
        index_task_id: str,
        material: CaseMaterial,
    ) -> DiagnosisCaseRecord: ...
