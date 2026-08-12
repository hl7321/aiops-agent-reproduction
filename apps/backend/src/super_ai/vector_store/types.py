"""Milvus client 的可注入窄 Protocol。"""

from __future__ import annotations

from typing import Any, Protocol


class MilvusClientProtocol(Protocol):
    def has_collection(self, collection_name: str, **kwargs: Any) -> bool: ...

    def create_collection(
        self,
        collection_name: str,
        *,
        schema: Any,
        index_params: Any,
        **kwargs: Any,
    ) -> None: ...

    def load_collection(self, collection_name: str, **kwargs: Any) -> None: ...

    def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    def search(self, **kwargs: Any) -> list[list[dict[str, Any]]]: ...

    def delete(
        self,
        collection_name: str,
        *,
        filter: str,
        **kwargs: Any,
    ) -> dict[str, int]: ...

    def get_server_version(self, **kwargs: Any) -> str | dict[str, Any]: ...


class MilvusClientFactory(Protocol):
    def __call__(self, *, uri: str, token: str) -> MilvusClientProtocol: ...
