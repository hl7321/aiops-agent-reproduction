"""供后续规范化领域 adapter 复用的 SQLite Repository 基类。"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.memory.records import Record

RecordT = TypeVar("RecordT", bound=Record)
ModelT = TypeVar("ModelT")


class SqliteRepository(Generic[RecordT, ModelT], ABC):
    """只在 adapter 内部完成 record/ORM 转换和当前事务 flush。"""

    model_type: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: RecordT) -> None:
        self._session.add(self.to_model(record))
        await self._session.flush()

    async def get(self, record_id: str) -> RecordT | None:
        model = await self._session.get(self.model_type, record_id)
        if model is None:
            return None
        return self.to_record(model)

    @abstractmethod
    def to_model(self, record: RecordT) -> ModelT:
        """把 immutable record 转换为 adapter 内部 ORM model。"""

    @abstractmethod
    def to_record(self, model: ModelT) -> RecordT:
        """把 ORM model 转换为领域可见 immutable record。"""
