from pymilvus import DataType

from super_ai.vector_store.schema import build_collection_schema, build_index_params


def test_collection_schema_has_explicit_fields_and_1024_float_vector() -> None:
    schema = build_collection_schema().to_dict()
    fields = {field["name"]: field for field in schema["fields"]}

    assert schema["auto_id"] is False
    assert schema["enable_dynamic_field"] is False
    assert set(fields) == {
        "chunkId",
        "documentId",
        "knowledgeBaseId",
        "ownerUserId",
        "tenantId",
        "content",
        "source",
        "createdAt",
        "metadata",
        "vector",
    }
    assert fields["chunkId"]["type"] == DataType.VARCHAR
    assert fields["chunkId"]["is_primary"] is True
    assert fields["metadata"]["type"] == DataType.JSON
    assert fields["vector"]["type"] == DataType.FLOAT_VECTOR
    assert fields["vector"]["params"] == {"dim": 1024}


def test_index_params_fix_scalar_and_hnsw_cosine_contract() -> None:
    indexes = {index.field_name: index.to_dict() for index in build_index_params()}

    assert set(indexes) == {"tenantId", "knowledgeBaseId", "documentId", "vector"}
    for field_name in ("tenantId", "knowledgeBaseId", "documentId"):
        assert indexes[field_name]["index_type"] == "INVERTED"
    assert indexes["vector"] == {
        "field_name": "vector",
        "index_name": "vector_hnsw",
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "M": 16,
        "efConstruction": 200,
    }
