from collections.abc import Iterator
from typing import Any

class IndexParam:
    field_name: str
    index_name: str
    index_type: str
    def to_dict(self) -> dict[str, Any]: ...

class IndexParams:
    def add_index(
        self,
        field_name: str,
        index_type: str = ...,
        index_name: str = ...,
        **kwargs: Any,
    ) -> None: ...
    def __iter__(self) -> Iterator[IndexParam]: ...
