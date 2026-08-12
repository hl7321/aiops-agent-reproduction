"""认证身份到 tenant/owner scope 的不可变值对象。"""

from __future__ import annotations

from dataclasses import dataclass


def _nonempty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不得为空")
    return normalized


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _nonempty(self.user_id, "user_id"))

    @property
    def tenant_id(self) -> str:
        return self.user_id

    @property
    def owner_user_id(self) -> str:
        return self.user_id


@dataclass(frozen=True, slots=True)
class OwnerScope:
    tenant_id: str
    owner_user_id: str

    def __post_init__(self) -> None:
        tenant_id = _nonempty(self.tenant_id, "tenant_id")
        owner_user_id = _nonempty(self.owner_user_id, "owner_user_id")
        if tenant_id != owner_user_id:
            raise ValueError("当前本地模型要求 tenant_id 等于 owner_user_id")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "owner_user_id", owner_user_id)


@dataclass(frozen=True, slots=True)
class TenantContext:
    current_user: CurrentUser
    owner_scope: OwnerScope

    def __post_init__(self) -> None:
        if self.current_user.user_id != self.owner_scope.owner_user_id:
            raise ValueError("tenant context scope 必须属于当前用户")

    @classmethod
    def from_current_user(cls, current_user: CurrentUser) -> TenantContext:
        return cls(
            current_user=current_user,
            owner_scope=OwnerScope(
                tenant_id=current_user.tenant_id,
                owner_user_id=current_user.owner_user_id,
            ),
        )

    @property
    def tenant_id(self) -> str:
        return self.owner_scope.tenant_id
