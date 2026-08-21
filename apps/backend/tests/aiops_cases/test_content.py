from super_ai.aiops.cases.content import build_case_material


def test_case_material_is_honest_bounded_and_traceable() -> None:
    material = build_case_material(
        task_id="task-1",
        report_id="report-1",
        report_markdown=(
            "# 告警分析报告\n## 📋 活跃告警清单\n- HighError / checkout\n"
            "## 🔍 告警根因分析1\n- 根因结论：连接池耗尽\n"
            "## 🛠️ 处理方案执行1\n- 建议：扩容连接池\n## 📊 结论\n- 整体评估：已定位"
        ),
        alerts=({"alertName": "HighError", "service": "checkout"},),
        evidence_ids=(),
    )
    assert material.alert_name == "HighError"
    assert material.service == "checkout"
    assert material.evidence_ids == ()
    assert "knowledgeType: diagnostic-case" in material.markdown
    assert "sourceTaskId: task-1" in material.markdown
    assert material.source_metadata["sourceReportId"] == "report-1"


def test_case_material_uses_first_real_alert_and_marks_missing_conclusions() -> None:
    material = build_case_material(
        task_id="task-1",
        report_id="report-1",
        report_markdown="# 告警分析报告\n只有已确认的事实",
        alerts=(
            {"alertName": "First", "service": "gateway"},
            {"alertName": "Second", "service": "worker"},
        ),
        evidence_ids=("e-1", "e-1", "", "e-2"),
    )
    assert material.alert_name == "First"
    assert material.service == "gateway"
    assert material.evidence_ids == ("e-1", "e-2")
    assert "证据不足" in material.root_cause
    assert "证据不足" in material.remediation
    assert len(material.summary) <= 2000
