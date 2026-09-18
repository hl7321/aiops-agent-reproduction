"""诊断计划、重规划与 Qwen structured-output 边界。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from super_ai.aiops.models import DiagnosticEvidenceRecord, PlanStep
from super_ai.aiops.tool_policy import ToolCapabilityDescriptor
from super_ai.aiops.tool_schema import tool_schema_properties, tool_schema_required
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
) -> dict[str, JsonValue]:
    """把模型参数收敛到服务端权威范围。

    这里只做两件事：注入服务端权威字段（Region/TopicId），以及按官方 schema 过滤非法键。
    别名映射、默认时间窗、默认查询、秒级换算与时间窗重置都已删除——它们的作用是替模型
    猜错买单，让参数错误失去反馈。参数是否合法由官方 schema 校验决定；不合法就直接报错，
    由纠错路径把完整参数说明和字段错误交回模型修正。
    """
    region = defaults.region.strip()
    topic_id = defaults.topic_id.strip()
    if not region or not topic_id:
        raise ValueError("clsLogUpload region/topicId 配置缺失")
    raw_properties = tool_schema_properties(schema)
    if not raw_properties:
        raise ValueError("SearchLog 工具缺少可验证的 properties schema")
    allowed = set(raw_properties)
    normalized: dict[str, JsonValue] = {
        key: value for key, value in arguments.items() if key in allowed
    }
    if "Region" in allowed:
        normalized["Region"] = region
    if "TopicId" in allowed:
        normalized["TopicId"] = topic_id

    required = tool_schema_required(schema)
    missing = [key for key in required if key not in normalized]
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
    requires_temporal_context: bool = Field(default=False, alias="requiresTemporalContext")


class ReplanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DiagnosticReplanAction
    steps: list[PlanStepDraft] = Field(default_factory=_empty_plan_steps)
    reason: str = Field(min_length=1, max_length=500)
    requires_temporal_context: bool = Field(default=False, alias="requiresTemporalContext")


class ToolArgumentRepairDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arguments: dict[str, JsonValue]


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
    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft: ...

    async def repair_tool_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        argument_keys: Sequence[str],
        validation_errors: Sequence[str],
    ) -> ToolArgumentRepairDraft: ...

    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft: ...

    async def report(self, *, context: str) -> ReportDraft: ...


class QwenDiagnosticModel:
    """只在 handler 显式运行时调用注入的 Qwen ChatOpenAI。"""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft:
        runnable = self._model.with_structured_output(PlanDraft)
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是证据优先的 AIOps Planner。只使用给出的工具，生成 1 到 8 步计划；"
                        "计划必须且只能包含一个真实 SearchLog 类工具步骤。"
                        "未验证查询先用 query_builder；仅当结论依赖调用顺序、重试、"
                        "熔断或恢复时才声明 requiresTemporalContext 并在 SearchLog 后使用"
                        " log_context。"
                    )
                ),
                HumanMessage(
                    content=(
                        f"可用能力：{_catalog_payload(tool_catalog)}\n"
                        f"上次计划校验错误：{list(validation_errors)}\n"
                        f"安全上下文：\n{context}"
                    )
                ),
            ]
        )
        return PlanDraft.model_validate(result)

    async def repair_tool_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        argument_keys: Sequence[str],
        validation_errors: Sequence[str],
    ) -> ToolArgumentRepairDraft:
        runnable = self._model.with_structured_output(ToolArgumentRepairDraft)
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "修正只读 AIOps 工具的非权威参数。只依据允许 Schema 和字段错误；"
                        "不得生成 Region、TopicId、owner、凭据或跨步骤定位字段。"
                    )
                ),
                HumanMessage(
                    content=(
                        f"工具：{_catalog_payload((tool,))}\n"
                        f"现有参数键：{list(argument_keys)}\n"
                        f"校验错误：{list(validation_errors)}\n上下文：{context}"
                    )
                ),
            ]
        )
        return ToolArgumentRepairDraft.model_validate(result)

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


def validate_plan(
    draft: PlanDraft,
    registered_tool_names: Sequence[str],
    *,
    query_is_trusted: bool = True,
) -> tuple[PlanStep, ...]:
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
    search_position = search_steps[0].position
    builders = [step for step in steps if is_query_builder_tool(step.tool_name)]
    if query_is_trusted and builders:
        raise ValueError("服务端已有可信 Query，无需重复调用 TextToSearchLogQuery")
    if not query_is_trusted:
        if len(builders) != 1 or builders[0].position >= search_position:
            raise ValueError("未验证 Query 必须先调用一次 TextToSearchLogQuery")
    contexts = [step for step in steps if is_log_context_tool(step.tool_name)]
    if draft.requires_temporal_context:
        if len(contexts) != 1 or contexts[0].position <= search_position:
            raise ValueError("时序结论必须在 SearchLog 后调用一次 DescribeLogContext")
    elif contexts:
        raise ValueError("非时序计划不得为凑步骤调用 DescribeLogContext")
    return steps


async def create_validated_plan(
    model: DiagnosticModel,
    *,
    context: str,
    tool_catalog: Sequence[ToolCapabilityDescriptor],
    query_is_trusted: bool,
    max_attempts: int = 3,
) -> tuple[PlanStep, ...]:
    if max_attempts < 1 or max_attempts > 3:
        raise ValueError("Planner 校验纠错次数必须在 1..3")
    errors: list[str] = []
    registered_names = tuple(item.name for item in tool_catalog)
    for _attempt in range(1, max_attempts + 1):
        draft = await model.plan(
            context=context,
            tool_catalog=tool_catalog,
            validation_errors=tuple(errors),
        )
        try:
            return validate_plan(
                draft, registered_names, query_is_trusted=query_is_trusted
            )
        except ValueError as error:
            errors.append(str(error)[:500])
    raise ValueError(f"Planner 三次校验纠错后仍无有效计划: {errors[-1]}")


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


def is_query_builder_tool(name: str) -> bool:
    return re.sub(r"[_\-\s]+", "", name.casefold()) == "texttosearchlogquery"


def is_log_context_tool(name: str) -> bool:
    return re.sub(r"[_\-\s]+", "", name.casefold()) == "describelogcontext"


def _catalog_payload(
    catalog: Sequence[ToolCapabilityDescriptor],
) -> list[dict[str, object]]:
    return [
        {
            "name": item.name,
            "description": item.description,
            "inputSchema": item.input_schema,
            "capability": item.capability,
            "dependencies": list(item.dependencies),
            "requiredForProfile": item.required_for_profile,
        }
        for item in catalog
    ]


def summarize_evidence(evidence: Sequence[DiagnosticEvidenceRecord]) -> str:
    return "\n".join(
        f"- evidenceId={item.id}; kind={item.kind}; title={item.title}; summary={item.summary}"
        for item in evidence
    )
