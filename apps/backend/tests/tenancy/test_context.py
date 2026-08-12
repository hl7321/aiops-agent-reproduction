from dataclasses import FrozenInstanceError

import pytest

from super_ai.auth.models import AuthPrincipal, UserRecord
from super_ai.tenancy.context import CurrentUser, OwnerScope, TenantContext
from super_ai.tenancy.dependencies import get_current_user


def test_current_user_builds_equal_nonempty_tenant_and_owner_scope() -> None:
    current_user = CurrentUser(user_id="user-a")
    context = TenantContext.from_current_user(current_user)

    assert context.current_user == current_user
    assert context.tenant_id == "user-a"
    assert context.owner_scope == OwnerScope(tenant_id="user-a", owner_user_id="user-a")
    with pytest.raises(FrozenInstanceError):
        current_user.user_id = "user-b"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("tenant_id", "owner_user_id"),
    [("", "user-a"), ("user-a", ""), ("user-a", "user-b"), (" ", "user-a")],
)
def test_owner_scope_rejects_empty_or_mismatched_identity(
    tenant_id: str,
    owner_user_id: str,
) -> None:
    with pytest.raises(ValueError):
        OwnerScope(tenant_id=tenant_id, owner_user_id=owner_user_id)


def test_tenant_context_rejects_scope_for_another_user() -> None:
    with pytest.raises(ValueError):
        TenantContext(
            current_user=CurrentUser(user_id="user-a"),
            owner_scope=OwnerScope(tenant_id="user-b", owner_user_id="user-b"),
        )


async def test_bearer_principal_maps_to_current_user_and_tenant_scope() -> None:
    principal = AuthPrincipal(
        user=UserRecord(email="user@example.com", password_hash="not-exposed"),
        session_id="session-1",
    )

    current_user = await get_current_user(principal)
    context = TenantContext.from_current_user(current_user)

    assert current_user.user_id == principal.user.id
    assert context.tenant_id == principal.user.id
    assert context.owner_scope.owner_user_id == principal.user.id
