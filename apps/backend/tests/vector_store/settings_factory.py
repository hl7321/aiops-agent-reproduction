from super_ai.vector_store.config import VectorStoreSettings


def make_vector_store_settings() -> VectorStoreSettings:
    return VectorStoreSettings.model_validate(
        {
            "uri": "http://milvus.example:19530",
            "token": "local-token",
            "collectionName": "super_ai_chunks",
        }
    )
