"""一次诊断的结构化执行结果：由代码组装，接口与模型上下文共用同一份。

它同时承担三件事：

1. 给 Replanner 与报告节点一份真实执行记录；
2. 给前端一份"这次点击到底发生了什么"的可读总账（含各阶段耗时）；
3. 作为唯一事实来源，避免前端重复实现同一套分组与脱敏逻辑。

参数只输出**键名**不输出取值：`Region`/`TopicId` 这类服务端注入字段的值不应离开后端。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import cast

from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticStepRecord,
    DiagnosticTaskRecord,
    PlanStep,
)
from super_ai.aiops.tool_failures import failure_class_of
from super_ai.project_config import JsonValue


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def _duration_ms(started: datetime | None, completed: datetime | None) -> int | None:
    if started is None or completed is None:
        return None
    return max(0, int((completed - started).total_seconds() * 1000))


def _stage(
    name: str, started: datetime | None, completed: datetime | None
) -> dict[str, JsonValue]:
    return {
        "name": name,
        "startedAt": _iso(started),
        "completedAt": _iso(completed),
        "durationMs": _duration_ms(started, completed),
    }


def _stages(
    task: DiagnosticTaskRecord | None,
    steps: Sequence[DiagnosticStepRecord],
) -> list[JsonValue]:
    """按任务与步骤的时间戳切出可解释的阶段耗时。

    分界依据是真实记录而不是猜测：受理到开始、开始到首个步骤、首个步骤到最后一个步骤结束、
    最后到完成。没有时间戳的阶段留空，不编造数值。
    """
    if task is None:
        return []
    ordered = sorted(
        (item for item in steps if item.started_at is not None),
        key=lambda item: cast(datetime, item.started_at),
    )
    first_started = ordered[0].started_at if ordered else None
    last_completed = None
    for item in reversed(ordered):
        if item.completed_at is not None:
            last_completed = item.completed_at
            break
    return [
        _stage("受理", task.created_at, task.started_at),
        _stage("规划", task.started_at, first_started),
        _stage("执行", first_started, last_completed),
        _stage("报告", last_completed, task.completed_at),
    ]


def build_execution_result(
    plan: Sequence[PlanStep],
    steps: Sequence[DiagnosticStepRecord],
    evidence: Sequence[DiagnosticEvidenceRecord],
    *,
    task: DiagnosticTaskRecord | None = None,
) -> dict[str, JsonValue]:
    attempts_by_position: dict[int, list[DiagnosticStepRecord]] = {}
    for item in steps:
        attempts_by_position.setdefault(item.position, []).append(item)
    evidence_by_step: dict[str, list[DiagnosticEvidenceRecord]] = {}
    for item in evidence:
        if item.diagnostic_step_id:
            evidence_by_step.setdefault(item.diagnostic_step_id, []).append(item)

    entries: list[JsonValue] = []
    for step in plan:
        attempts = sorted(
            attempts_by_position.get(step.position, []), key=lambda item: item.attempt
        )
        last = attempts[-1] if attempts else None
        entries.append(
            cast(JsonValue, {
                "position": step.position,
                "toolName": step.tool_name,
                "purpose": step.purpose,
                "executed": bool(attempts),
                "status": last.status if last is not None else "pending",
                "resultSummary": last.result_summary if last is not None else None,
                "startedAt": _iso(attempts[0].started_at if attempts else None),
                "completedAt": _iso(last.completed_at if last is not None else None),
                "durationMs": _duration_ms(
                    attempts[0].started_at if attempts else None,
                    last.completed_at if last is not None else None,
                ),
                "attempts": [
                    {
                        "attempt": item.attempt,
                        "status": item.status,
                        # 只给参数键，不给取值：Region/TopicId 的值不离开后端。
                        "argumentKeys": sorted(item.arguments),
                        "failureClass": failure_class_of(item.error_category),
                        "errorCategory": item.error_category,
                        "errorMessage": item.error_message,
                        "resultSummary": item.result_summary,
                        "startedAt": _iso(item.started_at),
                        "completedAt": _iso(item.completed_at),
                        "durationMs": _duration_ms(item.started_at, item.completed_at),
                    }
                    for item in attempts
                ],
                "producedEvidence": [
                    {
                        "evidenceId": item.id,
                        "kind": item.kind,
                        "summary": item.summary[:600],
                    }
                    for attempt in attempts
                    for item in evidence_by_step.get(attempt.id, [])
                ],
            })
        )

    evidence_by_kind: dict[str, int] = {}
    for item in evidence:
        evidence_by_kind[item.kind] = evidence_by_kind.get(item.kind, 0) + 1
    return {
        "taskId": task.id if task is not None else None,
        "createdAt": _iso(task.created_at if task is not None else None),
        "startedAt": _iso(task.started_at if task is not None else None),
        "completedAt": _iso(task.completed_at if task is not None else None),
        # 总耗时从"任务被创建"算起，而不是从"工作进程接手"算起：
        # 这样它正好等于四个阶段耗时之和（受理 + 规划 + 执行 + 报告），
        # 页面上的阶段条加起来不会和总耗时对不上。
        "durationMs": _duration_ms(
            task.created_at if task is not None else None,
            task.completed_at if task is not None else None,
        ),
        "stages": _stages(task, steps),
        "plan": entries,
        "evidenceByKind": cast(JsonValue, evidence_by_kind),
    }
