"""Milvus collection schema 和 index builder。"""

from pymilvus import CollectionSchema, DataType, MilvusClient
from pymilvus.milvus_client.index import IndexParams

VECTOR_DIMENSIONS = 1024
SEARCH_EF = 64
IDENTIFIER_MAX_LENGTH = 128
SOURCE_MAX_LENGTH = 2048
CONTENT_MAX_LENGTH = 65535
TIMESTAMP_MAX_LENGTH = 64


def build_collection_schema() -> CollectionSchema:
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(
        field_name="chunkId",
        datatype=DataType.VARCHAR,
        is_primary=True,
        max_length=IDENTIFIER_MAX_LENGTH,
    )
    for field_name in ("documentId", "knowledgeBaseId", "ownerUserId", "tenantId"):
        schema.add_field(
            field_name=field_name,
            datatype=DataType.VARCHAR,
            max_length=IDENTIFIER_MAX_LENGTH,
        )
    schema.add_field(
        field_name="content",
        datatype=DataType.VARCHAR,
        max_length=CONTENT_MAX_LENGTH,
    )
    schema.add_field(
        field_name="source",
        datatype=DataType.VARCHAR,
        max_length=SOURCE_MAX_LENGTH,
    )
    schema.add_field(
        field_name="createdAt",
        datatype=DataType.VARCHAR,
        max_length=TIMESTAMP_MAX_LENGTH,
    )
    schema.add_field(field_name="metadata", datatype=DataType.JSON)
    schema.add_field(
        field_name="vector",
        datatype=DataType.FLOAT_VECTOR,
        dim=VECTOR_DIMENSIONS,
    )
    return schema


def build_index_params() -> IndexParams:
    indexes = MilvusClient.prepare_index_params()
    indexes.add_index(
        field_name="vector",
        index_name="vector_hnsw",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    for field_name in ("tenantId", "knowledgeBaseId", "documentId"):
        indexes.add_index(
            field_name=field_name,
            index_name=f"{field_name}_inverted",
            index_type="INVERTED",
        )
    return indexes
