from enum import IntEnum
from typing import Any

from pymilvus.milvus_client.index import IndexParams

class DataType(IntEnum):
    VARCHAR: DataType
    JSON: DataType
    FLOAT_VECTOR: DataType

class CollectionSchema:
    def add_field(
        self,
        field_name: str,
        datatype: DataType,
        **kwargs: Any,
    ) -> CollectionSchema: ...
    def to_dict(self) -> dict[str, Any]: ...

class MilvusClient:
    def __init__(
        self,
        uri: str = ...,
        user: str = ...,
        password: str = ...,
        db_name: str = ...,
        token: str = ...,
        timeout: float | None = ...,
        **kwargs: Any,
    ) -> None: ...
    @classmethod
    def create_schema(cls, **kwargs: Any) -> CollectionSchema: ...
    @staticmethod
    def prepare_index_params(field_name: str = ..., **kwargs: Any) -> IndexParams: ...
