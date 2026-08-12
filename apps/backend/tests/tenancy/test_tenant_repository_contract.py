from super_ai.tenancy.repositories import validate_owner_scoped_repository


class GoodRepository:
    async def get(self, owner_user_id: str, resource_id: str) -> object | None:
        return None

    async def update(self, owner_user_id: str, resource_id: str, value: object) -> bool:
        return False

    async def delete(self, owner_user_id: str, resource_id: str) -> bool:
        return False


class MissingOwnerRepository:
    async def get(self, resource_id: str) -> object | None:
        return None


class MisorderedOwnerRepository:
    async def get(self, resource_id: str, owner_user_id: str) -> object | None:
        return None


def test_owner_scoped_repository_requires_first_business_parameter() -> None:
    validate_owner_scoped_repository(GoodRepository)


def test_repository_without_explicit_owner_parameter_is_rejected() -> None:
    for repository in (MissingOwnerRepository, MisorderedOwnerRepository):
        try:
            validate_owner_scoped_repository(repository)
        except TypeError as error:
            assert "owner_user_id" in str(error)
        else:
            raise AssertionError(f"{repository.__name__} 未被拒绝")
