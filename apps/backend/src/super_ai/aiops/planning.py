"""诊断计划、重规划与 Qwen structured-output 边界。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from super_ai.aiops.models import DiagnosticEvidenceRecord, PlanStep
from super_ai.aiops.tool_policy import ToolCapabilityDescriptor, normalized_tool_name
from super_ai.aiops.tool_schema import tool_schema_properties, tool_schema_required
from super_ai.api_contracts import DiagnosticReplanAction

MAX_PLAN_STEPS = 8
MAX_REPLANS = 3
# 每个计划步骤（按步骤位置计）最多两次尝试：第一次失败后只给一次重试机会。
# 分类已经把"不值得重试的"拦在一次以内，剩下需要第二次机会的主要是瞬时错误；
# 同时把最坏情况的调用数压在 8 步 × 2 = 16 次以内。
MAX_STEP_ATTEMPTS = 2


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

    tool_name: str = Field(
        alias="toolName",
        min_length=1,
        max_length=128,
        description="要使用的工具名。必须与「可用工具清单」中出现过的名称完全一致。",
    )
    purpose: str = Field(
        min_length=1,
        max_length=500,
        description="这一步要拿到什么信息、供后面哪一步使用，一句话说清。",
    )


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[PlanStepDraft] = Field(
        min_length=1,
        max_length=MAX_PLAN_STEPS,
        description="按执行顺序排列的步骤清单。每一步只说明用哪个工具、为什么用，不含参数值。",
    )
    requires_temporal_context: bool = Field(
        default=False,
        alias="requiresTemporalContext",
        description=(
            "这份计划是否需要事件前后顺序的证据。"
            "只有结论依赖调用顺序、重试、熔断或恢复时才填 true。"
        ),
    )


class StepArgumentsDraft(BaseModel):
    """执行者为当前这一步生成的工具参数。"""

    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "要交给当前工具执行的参数。键必须是该工具参数说明里出现过的字段名；"
            "说明里标了必填的必须提供；取值按说明的类型与取值范围。"
        ),
    )


class ReplanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DiagnosticReplanAction
    steps: list[PlanStepDraft] = Field(default_factory=_empty_plan_steps)
    reason: str = Field(min_length=1, max_length=500)
    requires_temporal_context: bool = Field(default=False, alias="requiresTemporalContext")


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


# 报告提示词写成模块常量，便于与 reporting.py 的结构校验做逐字对齐测试。
# 校验器要求的是**字面量**（含全角冒号），所以这里必须原样出现，不能只列字段名。
REPORT_SYSTEM_PROMPT = (
    "【角色定义】\n"
    "你是 AIOps 诊断报告撰写者。你只依据给出的告警、SOP、计划、执行结果与真实证据写一份"
    "中文 Markdown 报告。你不重新诊断，也不补充输入里没有的事实。\n\n"
    "【任务】\n"
    "按下面给出的固定结构，逐字照抄小标题与字段标签，写出一份完整报告。\n\n"
    "【该做什么】\n"
    "1. 先读执行结果：哪些步骤成功、哪些失败、产出了什么证据。\n"
    "2. 每条告警都写一组编号段落：`## 🔍 告警根因分析N` 与 `## 🛠️ 处理方案执行N`，"
    "N 从 1 开始并与告警顺序一致。\n"
    "3. 每一段内部必须逐字使用下列标签——注意是全角冒号「：」，不要写成半角「:」，"
    "也不要改标签名：\n"
    "   - 根因分析段内：详情： / 症状： / 日志证据： / 根因结论：\n"
    "   - 处理方案段内：已执行步骤： / 建议： / 预期效果：\n"
    "   - 结论段内：整体评估： / 关键发现： / 后续建议： / 风险评估：\n"
    "4. 证据不足时必须在报告中写明不确定性，不得编造根因、日志、指标或工具结果。\n"
    "5. claims[].evidenceIds 只能引用输入中出现过的证据 ID。\n\n"
    "【输出结果】\n"
    "输出 markdown，结构必须与下面这份示例完全一致（示例文字只是占位）：\n\n"
    "# 告警分析报告\n\n"
    "## 📋 活跃告警清单\n"
    "- <告警名> / <服务> / <级别>\n\n"
    "## 🔍 告警根因分析1\n"
    "- 详情：<这条告警的原始信息>\n"
    "- 症状：<观察到的现象>\n"
    "- 日志证据：<引用真实证据 ID 与内容；没有就写尚无可用真实证据>\n"
    "- 根因结论：<依据证据的结论；证据不足就明说>\n\n"
    "## 🛠️ 处理方案执行1\n"
    "- 已执行步骤：<来自执行结果>\n"
    "- 建议：<建议动作>\n"
    "- 预期效果：<预期效果，不得写成已发生的事实>\n\n"
    "## 📊 结论\n"
    "- 整体评估：<整体判断>\n"
    "- 关键发现：<关键点>\n"
    "- 后续建议：<下一步>\n"
    "- 风险评估：<风险与限制>\n"
)


class DiagnosticModel(Protocol):
    async def plan(
        self,
        *,
        context: str,
        tool_catalog: Sequence[ToolCapabilityDescriptor],
        validation_errors: Sequence[str] = (),
    ) -> PlanDraft: ...

    async def fill_step_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        plan: Sequence[PlanStep],
        step: PlanStep,
        previous_error: str | None = None,
    ) -> StepArgumentsDraft: ...

    async def replan(self, *, context: str, remaining_steps: Sequence[PlanStep]) -> ReplanDraft: ...

    async def report(self, *, context: str) -> ReportDraft: ...


class QwenDiagnosticModel:
    """只在 handler 显式运行时调用注入的 Qwen ChatOpenAI。"""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def fill_step_arguments(
        self,
        *,
        context: str,
        tool: ToolCapabilityDescriptor,
        plan: Sequence[PlanStep],
        step: PlanStep,
        previous_error: str | None = None,
    ) -> StepArgumentsDraft:
        runnable = self._model.with_structured_output(StepArgumentsDraft)
        plan_view = [
            {"step": item.position, "tool": item.tool_name, "purpose": item.purpose}
            for item in plan
        ]
        result = await runnable.ainvoke(
            [
                SystemMessage(
                    content=(
                        "【角色定义】\n"
                        "你是 AIOps 诊断的执行者。规划者已经定好了用哪些工具、按什么顺序查，"
                        "你站在执行位置：你不决定用什么工具，也不改顺序，完全按计划执行。"
                        "你只负责一件事——把当前这一步真正跑起来，办法是给它生成一份"
                        "能直接调用的参数。\n\n"
                        "【任务】\n"
                        "为当前这一步生成一份能直接交给工具执行的参数。\n\n"
                        "【该做什么】\n"
                        "1. 先看当前这一步是哪个工具、要拿到什么信息。\n"
                        "2. 看前面步骤的真实产出。这一步要用的值必须从里面原样取，不要自己编。\n"
                        "3. 看整份计划，理解这一步的产出会被后面哪一步用到。\n"
                        "4. 按当前工具的完整参数说明填：说明里标了必填的一定要填；类型与取值范围"
                        "按说明来；只填当前这个工具的参数；说明里没出现的字段不要自己造。\n"
                        "5. 如果给了「上一次的错误」，只针对那个错误修正，其他地方不要动。\n"
                        "6. 填不出来的字段不要瞎编。\n\n"
                        "【输出结果】\n"
                        "arguments：要交给当前工具执行的参数。\n"
                        "- 键必须是该工具参数说明里出现过的，不能自己造键名。\n"
                        "- 说明里标了必填的必须填上。\n"
                        "- 值的类型要跟说明一致。\n"
                        "- 这一步要用的值如果在前面的产出里，必须原样取过来，不要改写。\n"
                        "交出去之前自己检查一遍：有没有自创的键名？必填都填了吗？"
                        "每个值真的来自前面产出或告警吗？"
                    )
                ),
                HumanMessage(
                    content=(
                        f"【当前这一步】第 {step.position} 步 / 工具 {tool.name} / "
                        f"用途：{step.purpose}\n"
                        f"【当前工具的完整说明】{_catalog_payload((tool,))}\n"
                        f"【整份计划】{plan_view}\n"
                        f"【上下文】\n{context}\n"
                        f"【上一次的错误】{previous_error or '无'}"
                    )
                ),
            ]
        )
        return StepArgumentsDraft.model_validate(result)

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
                        "【角色定义】\n"
                        "你是 AIOps 诊断的规划者。你面前有一条已经触发的告警、一份同类故障的"
                        "处理经验（SOP），以及一份来自日志平台的真实工具清单。"
                        "你站在整条链路的起点：你只决定用哪些工具、按什么顺序查，不负责真正去查。"
                        "真正调用工具的是执行者，它会在执行到那一步时才去填具体参数。\n\n"
                        "【任务】\n"
                        "产出一份诊断计划：用哪几个工具、按什么顺序、每一步是为了拿到什么信息。\n\n"
                        "【该做什么】\n"
                        "1. 先读懂告警：哪个服务、什么现象、严重程度。\n"
                        "2. 读 SOP。它是同一类故障的处理经验，优先按它的思路选工具和顺序；"
                        "若检索到多份 SOP，先判断哪一份与当前告警是同一类故障，只参考那一份。\n"
                        "3. 从工具清单里选工具。清单里有名字的才能用，工具名必须一字不差照抄。\n"
                        "4. 排好步骤顺序，想清楚这一步的产出后面哪一步要用。\n"
                        "5. 每一步写一句用途，说清要拿到什么信息、给后面哪一步用。\n"
                        "6. 不要填任何工具参数。参数由执行者在那一步真正执行时填，"
                        "你现在写的值一定是凭空猜的，所以不要写。\n"
                        "7. 硬性约束（必须满足，否则计划会被打回重做）：\n"
                        "   - 步骤数在 1 到 8 之间；\n"
                        "   - 必须且只能有一个日志检索步骤；\n"
                        "   - 要做日志检索，就必须在它前面放一个生成查询的步骤；\n"
                        "   - 只有结论依赖调用顺序、重试、熔断或恢复这类时序判断时，"
                        "才在日志检索之后加一个查日志上下文的步骤；\n"
                        "   - 不要为了凑步骤而加工具。\n\n"
                        "【输出结果】\n"
                        "steps：按执行顺序排列的步骤清单，每一步包含：\n"
                        "  - toolName：工具名，必须与清单中出现的名称完全一致（大小写一致）；\n"
                        "  - purpose：这一步要拿到什么信息、给后面哪一步用，一句话说清；\n"
                        "    合格示例：「查 order-service 的日志主题 ID，供第 3 步使用」；\n"
                        "    不合格示例：「查一下主题」。\n"
                        "requiresTemporalContext：这份计划是否需要事件前后顺序的证据。\n"
                        "交出去之前自己检查一遍：步骤数在 1 到 8 之间吗？每个 toolName 都能"
                        "在清单里原样找到吗？有且只有一个日志检索步骤吗？它前面有生成查询的"
                        "步骤吗？每一步的 purpose 都写清了给谁用吗？"
                    )
                ),
                HumanMessage(
                    content=(
                        f"【可用工具清单】{_catalog_payload(tool_catalog)}\n"
                        f"【上一次计划被打回的原因】{list(validation_errors) or '无'}\n"
                        f"【上下文】\n{context}"
                    )
                ),
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
                SystemMessage(content=REPORT_SYSTEM_PROMPT),
                HumanMessage(content=context),
            ]
        )
        return ReportDraft.model_validate(result)


def validate_plan(
    draft: PlanDraft,
    registered_tool_names: Sequence[str],
) -> tuple[PlanStep, ...]:
    if not 1 <= len(draft.steps) <= MAX_PLAN_STEPS:
        raise ValueError("诊断计划必须包含 1 到 8 步")
    unknown = sorted(
        {
            item.tool_name
            for item in draft.steps
            if resolve_tool_name(item.tool_name, registered_tool_names) is None
        }
    )
    if unknown:
        raise ValueError(
            f"诊断计划引用了本轮未发现的工具: {', '.join(unknown)}；"
            f"当前可用工具: {', '.join(sorted(registered_tool_names))}"
        )
    steps = tuple(
        PlanStep(
            index,
            cast(str, resolve_tool_name(item.tool_name, registered_tool_names)),
            item.purpose,
            # 计划阶段不产出参数值：参数由执行者在执行该步骤时生成。
            {},
        )
        for index, item in enumerate(draft.steps)
    )
    search_steps = [step for step in steps if is_search_log_tool(step.tool_name)]
    if len(search_steps) != 1:
        raise ValueError("诊断计划必须且只能包含一个真实 SearchLog 类步骤")
    search_position = search_steps[0].position
    builders = [step for step in steps if is_query_builder_tool(step.tool_name)]
    if len(builders) != 1 or builders[0].position >= search_position:
        raise ValueError("要做日志检索，必须先调用一次 TextToSearchLogQuery 生成并验证 CQL")
    contexts = [step for step in steps if is_log_context_tool(step.tool_name)]
    if draft.requires_temporal_context:
        if len(contexts) != 1 or contexts[0].position <= search_position:
            raise ValueError("时序结论必须在 SearchLog 后调用一次 DescribeLogContext")
    elif contexts:
        raise ValueError("非时序计划不得为凑步骤调用 DescribeLogContext")
    return steps


def resolve_tool_name(candidate: str, registered_tool_names: Sequence[str]) -> str | None:
    """把计划里的工具名解析成本轮真实发现的名称。

    优先精确匹配；否则按语义登记表相同的归一化规则匹配，唯一命中才算解析成功。
    这样模型写成 `convert_time_string_to_timestamp` 也能被接受，而不是以
    "引用未注册工具"拒绝。
    """
    if candidate in registered_tool_names:
        return candidate
    normalized = normalized_tool_name(candidate)
    matches = [name for name in registered_tool_names if normalized_tool_name(name) == normalized]
    if len(matches) == 1:
        return matches[0]
    return None


def require_plan_step_at(plan: Sequence[PlanStep], position: int) -> PlanStep:
    """按进度指针取计划步骤，并断言位置字段与数组下标一致。"""
    step = plan[position]
    if step.position != position:
        raise ValueError(
            f"诊断计划位置与下标不一致: index={position} position={step.position}"
        )
    return step


async def create_validated_plan(
    model: DiagnosticModel,
    *,
    context: str,
    tool_catalog: Sequence[ToolCapabilityDescriptor],
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
            return validate_plan(draft, registered_names)
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
