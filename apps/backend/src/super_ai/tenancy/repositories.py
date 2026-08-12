"""受保护 Repository 的 owner 参数合同与签名治理。"""

from __future__ import annotations

import inspect
from typing import Protocol, TypeVar

RecordT = TypeVar("RecordT", covariant=True)
UpdateT = TypeVar("UpdateT", contravariant=True)
RepositoryT = TypeVar("RepositoryT", bound=type[object])


class OwnerScopedRepository(Protocol[RecordT, UpdateT]):
    async def get(self, owner_user_id: str, resource_id: str) -> RecordT | None: ...

    async def update(
        self,
        owner_user_id: str,
        resource_id: str,
        update: UpdateT,
    ) -> bool: ...

    async def delete(self, owner_user_id: str, resource_id: str) -> bool: ...


def validate_owner_scoped_repository(repository_type: type[object]) -> None:
    """拒绝公开方法未把 owner 放在首个业务参数的 Repository。"""
    methods = [
        (name, member)
        for name, member in repository_type.__dict__.items()
        if not name.startswith("_") and inspect.isfunction(member)
    ]
    if not methods:
        raise TypeError(f"{repository_type.__name__} 没有可验证的公开 Repository 方法")
    for name, member in methods:
        parameters = list(inspect.signature(member).parameters.values())
        if len(parameters) < 2 or parameters[1].name != "owner_user_id":
            raise TypeError(
                f"{repository_type.__name__}.{name} 的首个业务参数必须是 owner_user_id"
            )


def owner_scoped_repository(repository_type: RepositoryT) -> RepositoryT:
    validate_owner_scoped_repository(repository_type)
    return repository_type
