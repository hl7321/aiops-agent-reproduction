"""标准 SKILL.md 的无副作用安全解析器。"""

import json
import re
from datetime import date, datetime
from typing import cast

import yaml

from super_ai.chat_configuration.models import ParsedSkillDocument
from super_ai.project_config import JsonValue

MAX_SKILL_BYTES = 256 * 1024
MAX_NAME_CHARACTERS = 64
MAX_DESCRIPTION_CHARACTERS = 500
MAX_SUMMARY_CHARACTERS = 240
_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillDocumentValidationError(ValueError):
    """上传内容不符合稳定 Skill 合同。"""


def normalize_skill_name(value: str) -> str:
    normalized = re.sub(r"[-_\s]+", "-", value.strip().lower()).strip("-")
    if not normalized or len(normalized) > MAX_NAME_CHARACTERS:
        raise SkillDocumentValidationError("Skill name 长度无效")
    if _NAME_PATTERN.fullmatch(normalized) is None:
        raise SkillDocumentValidationError("Skill name 必须可规范化为 lowercase kebab-case")
    return normalized


def parse_skill_document(filename: str, payload: bytes) -> ParsedSkillDocument:
    if filename != "SKILL.md":
        raise SkillDocumentValidationError("文件名必须严格为 SKILL.md")
    if len(payload) > MAX_SKILL_BYTES:
        raise SkillDocumentValidationError("Skill 文件不得超过 256 KiB")
    try:
        content = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillDocumentValidationError("Skill 文件必须为 UTF-8") from error
    match = re.fullmatch(r"---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)", content, re.DOTALL)
    if match is None:
        raise SkillDocumentValidationError("Skill 必须包含 YAML frontmatter")
    try:
        raw_metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise SkillDocumentValidationError("Skill frontmatter 不是有效 YAML") from error
    if not isinstance(raw_metadata, dict):
        raise SkillDocumentValidationError("Skill frontmatter 根节点必须为对象")
    raw_map = cast(dict[object, object], raw_metadata)
    if not all(isinstance(key, str) for key in raw_map):
        raise SkillDocumentValidationError("Skill metadata key 必须为字符串")
    metadata = {cast(str, key): item for key, item in raw_map.items()}
    if _contains_non_json_yaml(metadata):
        raise SkillDocumentValidationError("Skill metadata 只能包含 JSON-safe 值")
    try:
        json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise SkillDocumentValidationError("Skill metadata 只能包含 JSON-safe 值") from error
    raw_name = metadata.get("name")
    raw_description = metadata.get("description")
    if not isinstance(raw_name, str) or not isinstance(raw_description, str):
        raise SkillDocumentValidationError("Skill 必须提供字符串 name 与 description")
    name = normalize_skill_name(raw_name)
    description = raw_description.strip()
    if not description or len(description) > MAX_DESCRIPTION_CHARACTERS:
        raise SkillDocumentValidationError("Skill description 长度无效")
    canonical = cast(dict[str, JsonValue], dict(metadata))
    canonical["description"] = description
    return ParsedSkillDocument(
        filename="SKILL.md",
        name=name,
        description=description,
        content=content,
        metadata=canonical,
        summary=description[:MAX_SUMMARY_CHARACTERS],
    )


def _contains_non_json_yaml(value: object) -> bool:
    if isinstance(value, (date, datetime, bytes, set, tuple)):
        return True
    if isinstance(value, dict):
        return any(
            not isinstance(key, str) or _contains_non_json_yaml(item)
            for key, item in cast(dict[object, object], value).items()
        )
    if isinstance(value, list):
        return any(_contains_non_json_yaml(item) for item in cast(list[object], value))
    return value is not None and not isinstance(value, (str, int, float, bool))
