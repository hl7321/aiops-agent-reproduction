import hashlib
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from super_ai.knowledge.chunking import (
    ChunkingConfig,
    DocumentChunkingService,
    chunk_document_text,
)
from super_ai.knowledge.files import MAX_UPLOAD_BYTES, UploadPolicyError, validate_and_extract


def test_markdown_policy_hash_and_all_size_boundaries() -> None:
    content = "# 标题\n\n正文".encode()
    extracted = validate_and_extract("guide.md", "text/markdown", content)
    assert extracted.text == "# 标题\n\n正文"
    assert extracted.sha256 == hashlib.sha256(content).hexdigest()
    for name, mime, body in [
        ("guide.txt", "text/plain", b"text"),
        ("guide.md", "text/plain", b"text"),
        ("guide.md", "text/markdown", b"\xff"),
        ("guide.md", "text/markdown", b""),
        ("guide.md", "text/markdown", b"x" * (MAX_UPLOAD_BYTES + 1)),
    ]:
        with pytest.raises(UploadPolicyError):
            validate_and_extract(name, mime, body)


def test_pdf_uses_injected_extractor_and_requires_text() -> None:
    extracted = validate_and_extract(
        "runbook.pdf", "application/pdf", b"%PDF-test", pdf_extractor=lambda _data: "第一页"
    )
    assert extracted.text == "第一页"
    with pytest.raises(UploadPolicyError):
        validate_and_extract(
            "empty.pdf", "application/pdf", b"%PDF-empty", pdf_extractor=lambda _data: "  "
        )


def test_real_pypdf_extracts_text_and_exact_size_limit_is_allowed() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}  # pyright: ignore[reportPrivateUsage]
            )
        }
    )
    stream = StreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 250 Td (Hello PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(  # pyright: ignore[reportPrivateUsage]
        stream
    )
    output = BytesIO()
    writer.write(output)
    assert (
        validate_and_extract("runbook.pdf", "application/pdf", output.getvalue()).text
        == "Hello PDF"
    )
    assert (
        validate_and_extract("maximum.md", "text/markdown", b"x" * MAX_UPLOAD_BYTES).size_bytes
        == MAX_UPLOAD_BYTES
    )


def test_three_splitters_and_config_validation() -> None:
    fixed = chunk_document_text("abcdefghij", ChunkingConfig(maxCharacters=6, overlap=2))
    assert [chunk.text for chunk in fixed] == ["abcdef", "efghij"]
    headings = chunk_document_text(
        "# A\nalpha\n## B\nbeta", ChunkingConfig(strategy="markdown-heading")
    )
    assert [chunk.metadata["headingPath"] for chunk in headings] == ["A", "A > B"]
    paragraphs = chunk_document_text(
        "one\nline\n\n two \n\n\nthree", ChunkingConfig(strategy="paragraph")
    )
    assert [chunk.text for chunk in paragraphs] == ["one\nline", "two", "three"]
    with pytest.raises(ValueError):
        ChunkingConfig(maxCharacters=10, overlap=10)
    with pytest.raises(ValueError):
        ChunkingConfig(strategy="paragraph", maxCharacters=10)


def test_preview_is_bounded_and_reuses_chunks() -> None:
    text = "\n\n".join("x" * 500 for _ in range(15))
    config = ChunkingConfig(strategy="paragraph")
    chunks = chunk_document_text(text, config)
    preview = DocumentChunkingService().preview(text, config)
    assert preview.total_chunks == len(chunks) == 15
    assert len(preview.items) == 12
    assert all(len(item.excerpt) <= 400 for item in preview.items)
    assert [item.index for item in preview.items] == list(range(12))
