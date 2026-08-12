from __future__ import annotations

from typing import Any

from super_ai.vector_store.types import MilvusClientProtocol


class FakeMilvusClient:
    def __init__(self, *, collection_exists: bool = False) -> None:
        self.collection_exists = collection_exists
        self.has_collection_calls: list[str] = []
        self.create_collection_calls: list[dict[str, Any]] = []
        self.load_collection_calls: list[str] = []
        self.insert_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.search_result: list[list[dict[str, Any]]] = [[]]
        self.server_version: str | dict[str, Any] = "3.0-beta"

    def has_collection(self, collection_name: str, **kwargs: Any) -> bool:
        self.has_collection_calls.append(collection_name)
        return self.collection_exists

    def create_collection(
        self,
        collection_name: str,
        *,
        schema: Any,
        index_params: Any,
        **kwargs: Any,
    ) -> None:
        self.create_collection_calls.append(
            {"collection_name": collection_name, "schema": schema, "index_params": index_params}
        )
        self.collection_exists = True

    def load_collection(self, collection_name: str, **kwargs: Any) -> None:
        self.load_collection_calls.append(collection_name)

    def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.insert_calls.append({"collection_name": collection_name, "data": data})
        return {"insert_count": len(data)}

    def search(self, **kwargs: Any) -> list[list[dict[str, Any]]]:
        self.search_calls.append(kwargs)
        return self.search_result

    def delete(
        self,
        collection_name: str,
        *,
        filter: str,
        **kwargs: Any,
    ) -> dict[str, int]:
        self.delete_calls.append({"collection_name": collection_name, "filter": filter})
        return {"delete_count": 1}

    def get_server_version(self, **kwargs: Any) -> str | dict[str, Any]:
        return self.server_version


class FakeMilvusClientFactory:
    def __init__(self, client: FakeMilvusClient) -> None:
        self.client = client
        self.calls: list[dict[str, str]] = []

    def __call__(self, *, uri: str, token: str) -> MilvusClientProtocol:
        self.calls.append({"uri": uri, "token": token})
        return self.client
