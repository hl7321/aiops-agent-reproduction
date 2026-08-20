from dataclasses import dataclass
from datetime import datetime

from super_ai.project_config import JsonValue


@dataclass(frozen=True, slots=True)
class ParsedSkillDocument:
    filename: str
    name: str
    description: str
    content: str
    metadata: dict[str, JsonValue]
    summary: str


@dataclass(frozen=True, slots=True)
class ChatPromptRecord:
    id: str
    owner_user_id: str
    label: str
    content: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatSkillRecord:
    id: str
    owner_user_id: str
    name: str
    description: str
    filename: str
    content: str
    metadata: dict[str, JsonValue]
    summary: str
    is_selected: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatConfigurationRecord:
    selected_prompt_id: str | None
    prompts: tuple[ChatPromptRecord, ...]
    skills: tuple[ChatSkillRecord, ...]
