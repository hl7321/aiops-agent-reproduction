from typing import cast

from super_ai.knowledge.vector import MilvusDocumentVectorDeleter
from super_ai.tenancy.context import OwnerScope
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.adapter import MilvusVectorStore


class RecordingVectorStore:
    def __init__(self) -> None:
        self.call: tuple[VectorScope, str, str] | None = None

    async def delete_document(
        self, scope: VectorScope, knowledge_base_id: str, document_id: str
    ) -> int:
        self.call = (scope, knowledge_base_id, document_id)
        return 1


async def test_vector_bridge_keeps_tenant_kb_document_delete_scope() -> None:
    store = RecordingVectorStore()
    deleter = MilvusDocumentVectorDeleter(cast(MilvusVectorStore, store))
    await deleter.delete_document(OwnerScope("user-a", "user-a"), "kb-a", "doc-a")
    assert store.call is not None
    scope, kb, document = store.call
    assert scope.tenant_id == scope.owner_user_id == "user-a"
    assert scope.allowed_knowledge_base_ids == ("kb-a",)
    assert (kb, document) == ("kb-a", "doc-a")
