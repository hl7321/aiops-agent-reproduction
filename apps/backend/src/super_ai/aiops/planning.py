"""诊断计划、重规划与 Qwen structured-output 边界。"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from super_ai.aiops.models import DiagnosticEvidenceRecord, PlanStep
from super_ai.api_contracts import DiagnosticReplanAction

MAX_PLAN_STEPS = 8
MAX_REPLANS = 3


@dataclass(frozen=True, slots=True)
class SearchLogQueryDefaults:
    region: str
    topic_id: str


def normalize_search_log_arguments(
    arguments: Mapping[str, JsonValue],
    *,
    schema: Mapping[str, object],
    defaults: SearchLogQueryDefaults,
    now_ms: Callable[[], int],
    fallback_query: str,
) -> dict[str, JsonValue]:
    """把 Planner 参数收敛到运行时发现的官方 SearchLog JSON Schema。"""
    raw_properties = schema.get("properties")
    if not isinstance(raw_properties, dict):
        raise ValueError("SearchLog 工具缺少可验证的 properties schema")
    properties = cast(dict[object, object], raw_properties)
    allowed = {str(key) for key in properties}
    normalized: dict[str, JsonValue] = {
        key: value for key, value in arguments.items() if key in allowed
    }
    aliases = {
        "Query": ("query", "logQuery", "q"),
        "Region": ("region",),
        "TopicId": ("topicId", "topic_id"),
        "Limit": ("limit",),
        "From": ("from",),
        "To": ("to",),
    }
    for canonical, candidates in aliases.items():
        if canonical not in allowed or canonical in normalized:
            continue
        for candidate in candidates:
            if candidate in arguments:
                normalized[canonical] = arguments[candidate]
                break

    current_ms = now_ms()
    normalized.setdefault("From", current_ms - 60 * 60 * 1000)
    normalized.setdefault("To", current_ms)
    normalized.setdefault("Query", fallback_query[:12_000])
    if defaults.region.strip():
        normalized.setdefault("Region", defaults.region.strip())
    if "TopicId" in allowed and defaults.topic_id.strip():
        normalized.setdefault("TopicId", defaults.topic_id.strip())

    raw_required = schema.get("required", ())
    required = cast(list[object], raw_required) if isinstance(raw_required, list) else []
    missing = [str(key) for key in required if isinstance(key, str) and key not in normalized]
    if missing:
        raise ValueError(f"SearchLog 参数缺少必填字段: {', '.join(missing)}")
    return {key: value for key, value in normalized.items() if key in allowed}


def _empty_plan_steps() -> list[PlanStepDraft]:
    return []


class PlanStepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(alias="toolName", min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=500)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[PlanStepDraft] = Field(min_length=1, max_length=MAX_PLAN_STEPS)


class ReplanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DiagnosticReplanAction
    steps: list[PlanStepDraft] = Field(default_factory=_empty_plan_steps)
    reason: str = Field(min_length=1, max_length=500)


class ReportClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_key: str = Field(alias="claimKey", min_length=1, max_length=128)
    section: str = Field(min_length=1, max_length=200)
    evidence_ids: list[str] = Field(alias="evidenceIds", min_length=1, max_length=50)
    uncertain: bool


def _empty_report_claims() -> list[ReportClaimDraft]:
    return []


class ReportDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=60_000)
    claims: list[ReportClaimDraft] = Field(default_factory=_empty_report_claims, max_length=100)
    uncertainty: bool


class DiagnosticModel(Protocol):
    async def plan(self, *, context: str, tool_names: Sequence[str]) -> PlanDraft: ...

    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft: ...

    async def report(self, *, context: str) -> ReportDraft: ...


class QwenDiagnosticModel:
    """只在 handler 显式运行时调用注入的 Qwen ChatOpenAI。"""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def plan(self, *, context: str, tool_names: Sequence[str]) -> PlanDraft:
        runnable = self._model.with_structured_output(PlanDraft)
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是证据优先的 AIOps Planner。只使用给出的工具，生成 1 到 8 步计划；"
                        "计划必须且只能包含一个真实 SearchLog 类工具步骤。"
                    )
                ),
                HumanMessage(content=f"可用工具：{list(tool_names)}\n安全上下文：\n{context}"),
            ]
        )
        return PlanDraft.model_validate(result)

    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft:
        runnable = self._model.with_structured_output(ReplanDraft)
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是 AIOps Replanner。只能依据已有证据决定 continue、replan 或 report；"
                        "不得补造成功或证据。"
                    )
                ),
                HumanMessage(content=f"剩余计划：{list(remaining_steps)}\n上下文：\n{context}"),
            ]
        )
        return ReplanDraft.model_validate(result)

    async def report(self, *, context: str) -> ReportDraft:
        runnable = self._model.with_structured_output(ReportDraft)
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "仅依据给出的告警、SOP、计划与真实证据生成中文 Markdown 报告。"
                        "固定结构必须包含 # 告警分析报告、## 📋 活跃告警清单、每条告警的"
                        "## 🔍 告警根因分析N（详情/症状/日志证据/根因结论）、"
                        "## 🛠️ 处理方案执行N（已执行步骤/建议/预期效果），以及"
                        "## 📊 结论（整体评估/关键发现/后续建议/风险评估）。"
                        "证据不足必须明确不确定性；每个关键 claims[].evidenceIds 只能引用"
                        "输入中出现的 ID。"
                    )
                ),
                HumanMessage(content=context),
            ]
        )
        return ReportDraft.model_validate(result)


def validate_plan(draft: PlanDraft, registered_tool_names: Sequence[str]) -> tuple[PlanStep, ...]:
    registered = set(registered_tool_names)
    steps = tuple(
        PlanStep(index, item.tool_name, item.purpose, item.arguments)
        for index, item in enumerate(draft.steps)
    )
    if not 1 <= len(steps) <= MAX_PLAN_STEPS:
        raise ValueError("诊断计划必须包含 1 到 8 步")
    unknown = sorted({step.tool_name for step in steps if step.tool_name not in registered})
    if unknown:
        raise ValueError(f"诊断计划引用未注册工具: {', '.join(unknown)}")
    search_steps = [step for step in steps if is_search_log_tool(step.tool_name)]
    if len(search_steps) != 1:
        raise ValueError("诊断计划必须且只能包含一个真实 SearchLog 类步骤")
    return steps


def find_search_log_tool(tool_names: Sequence[str]) -> str | None:
    matches = sorted(name for name in tool_names if is_search_log_tool(name))
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("发现多个 SearchLog 类工具，无法确定性选择")
    return matches[0]


def is_search_log_tool(name: str) -> bool:
    normalized = re.sub(r"[_\-\s]+", "", name.casefold())
    return normalized == "searchlog"


def summarize_evidence(evidence: Sequence[DiagnosticEvidenceRecord]) -> str:
    return "\n".join(
        f"- evidenceId={item.id}; kind={item.kind}; title={item.title}; summary={item.summary}"
        for item in evidence
    )
