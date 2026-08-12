"""领域服务可依赖的数据库无关 Repository 合同。"""

from typing import Protocol, TypeVar

from super_ai.memory.records import Record

RecordT = TypeVar("RecordT", bound=Record)


class Repository(Protocol[RecordT]):
    """最小 record 持久化合同；领域可声明更具体的 Protocol。"""

    async def add(self, record: RecordT) -> None:
        """加入当前事务但不自行提交。"""
        ...

    async def get(self, record_id: str) -> RecordT | None:
        """按基础标识返回 record，不暴露 ORM model。"""
        ...
