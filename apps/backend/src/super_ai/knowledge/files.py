"""Markdown/PDF 上传政策与文本提取。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FILE_TYPES = {".md": "text/markdown", ".pdf": "application/pdf"}
PdfExtractor = Callable[[bytes], str]


class UploadPolicyError(ValueError):
    """上传内容不满足权威 policy。"""


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    filename: str
    size_bytes: int
    mime_type: str
    sha256: str
    text: str


def validate_and_extract(
    filename: str,
    mime_type: str,
    content: bytes,
    *,
    pdf_extractor: PdfExtractor | None = None,
) -> ExtractedDocument:
    safe_name = Path(filename).name.strip()
    extension = Path(safe_name).suffix.casefold()
    expected_mime = ALLOWED_FILE_TYPES.get(extension)
    if not safe_name or expected_mime is None or mime_type.casefold() != expected_mime:
        raise UploadPolicyError("只允许扩展名与 MIME 匹配的 Markdown 或 PDF")
    size = len(content)
    if size == 0 or size > MAX_UPLOAD_BYTES:
        raise UploadPolicyError("文件必须大于零且不超过 10 MiB")
    if extension == ".md":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UploadPolicyError("Markdown 必须使用 UTF-8 编码") from error
    else:
        try:
            text = (pdf_extractor or extract_pdf_text)(content)
        except UploadPolicyError:
            raise
        except Exception as error:
            raise UploadPolicyError("PDF 无法解析") from error
    if not text.strip():
        raise UploadPolicyError("文档没有可索引文本")
    return ExtractedDocument(
        filename=safe_name,
        size_bytes=size,
        mime_type=expected_mime,
        sha256=sha256(content).hexdigest(),
        text=text,
    )


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
