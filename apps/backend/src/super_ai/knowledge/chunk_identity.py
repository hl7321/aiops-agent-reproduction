import hashlib


def stable_chunk_id(document_id: str, index: int, content: str) -> str:
    normalized_document_id = document_id.strip()
    if not normalized_document_id or index < 0 or not content:
        raise ValueError("document_id、非负 index 与 content 均为必填")
    digest = hashlib.sha256(
        f"{normalized_document_id}\0{index}\0{content}".encode()
    ).hexdigest()[:16]
    return f"{normalized_document_id}:{index}:{digest}"
