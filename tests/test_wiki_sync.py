from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sync_wiki import (
    SyncError,
    audit_counts,
    audit_delta_sync,
    audit_includes,
    main,
    sync_repository,
    validate_openspec_symlink,
)


def _write(path: Path, content: str = "# 内容\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_change(root: Path, name: str, *, archived: bool = False) -> Path:
    base = root / "openspec" / "changes"
    change = base / "archive" / name if archived else base / name
    _write(change / ".openspec.yaml", "schema: spec-driven\n")
    _write(change / "proposal.md", "# 提案\n")
    _write(change / "design.md", "# 设计\n")
    _write(change / "tasks.md", "# 任务\n")
    _write(
        change / "specs" / "sample-capability" / "spec.md",
        """## ADDED Requirements

### Requirement: 可发布规格
系统 MUST 发布规格。

#### Scenario: 发布成功
- **WHEN** 执行同步
- **THEN** 页面存在
""",
    )
    return change


def _create_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "openspec" / "changes" / "archive").mkdir(parents=True)
    _write(
        root / "openspec" / "specs" / "sample-capability" / "spec.md",
        """## Purpose

测试主规格。

## Requirements

### Requirement: 可发布规格
系统 MUST 发布规格。

#### Scenario: 发布成功
- **WHEN** 执行同步
- **THEN** 页面存在
""",
    )
    (root / "docs" / "openspec").symlink_to("../openspec", target_is_directory=True)
    return root


def test_active_sync_is_deterministic_and_preserves_created_date(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "z-change")
    _create_change(root, "a-change")

    first = sync_repository(root, "active", today=date(2026, 8, 23))
    page = root / "docs" / "changes" / "active" / "a-change" / "index.md"
    first_content = page.read_text(encoding="utf-8")

    second = sync_repository(root, "active", today=date(2026, 9, 1))

    assert first.active_changes == ("a-change", "z-change")
    assert second.active_changes == first.active_changes
    assert page.read_text(encoding="utf-8") == first_content
    assert "createdDate: 2026-08-23" in first_content
    assert "../../../openspec/changes/a-change/proposal.md" in first_content


def test_all_sync_generates_archive_specs_indexes_and_sidebar(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "active-change")
    _create_change(root, "2026-08-22-archived-change", archived=True)

    summary = sync_repository(root, "all", today=date(2026, 8, 23))

    archive_page = (
        root
        / "docs"
        / "changes"
        / "archive"
        / "2026-08-22-archived-change"
        / "index.md"
    )
    assert summary.active_changes == ("active-change",)
    assert summary.archived_changes == ("2026-08-22-archived-change",)
    assert summary.main_specs == ("sample-capability",)
    assert "archivedDate: 2026-08-22" in archive_page.read_text(encoding="utf-8")
    assert "@include:" in (archive_page.parent / "proposal.md").read_text(encoding="utf-8")
    assert (root / "docs" / "specs" / "sample-capability" / "index.md").is_file()
    assert (root / "docs" / "specs" / "index.md").is_file()
    assert (root / "docs" / "changes" / "index.md").is_file()
    assert (root / "docs" / ".vitepress" / "openspec-sidebar.generated.mts").is_file()


def test_sync_removes_only_stale_generated_pages(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "kept-change")
    stale = root / "docs" / "changes" / "active" / "stale-change" / "index.md"
    handwritten = root / "docs" / "changes" / "notes.md"
    _write(stale)
    _write(handwritten, "人工文档\n")

    sync_repository(root, "active", today=date(2026, 8, 23))

    assert not stale.parent.exists()
    assert handwritten.read_text(encoding="utf-8") == "人工文档\n"


def test_validate_symlink_accepts_only_expected_relative_target(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)

    validate_openspec_symlink(root)
    assert (root / "docs" / "openspec").readlink() == Path("../openspec")


@pytest.mark.parametrize("replacement", ["directory", "wrong-link", "missing"])
def test_validate_symlink_reports_actionable_windows_guidance(
    tmp_path: Path, replacement: str
) -> None:
    root = _create_repo(tmp_path)
    link = root / "docs" / "openspec"
    link.unlink()
    if replacement == "directory":
        link.mkdir()
    elif replacement == "wrong-link":
        link.symlink_to("../other", target_is_directory=True)

    with pytest.raises(SyncError, match="Developer Mode") as exc_info:
        validate_openspec_symlink(root)

    message = str(exc_info.value)
    assert "git config core.symlinks true" in message
    assert "不得复制" in message


def test_delta_audit_accepts_added_modified_removed_and_renamed(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    change = _create_change(root, "2026-08-23-delta-change", archived=True)
    _write(
        change / "specs" / "sample-capability" / "spec.md",
        """## ADDED Requirements

### Requirement: 新要求
新增。

#### Scenario: 新场景
- **WHEN** 新增
- **THEN** 存在

## MODIFIED Requirements

### Requirement: 已修改要求
修改。

#### Scenario: 修改后场景
- **WHEN** 修改
- **THEN** 更新

## REMOVED Requirements

### Requirement: 已删除要求
**Reason**: 不再需要
**Migration**: 无

## RENAMED Requirements

- FROM: `### Requirement: 旧名称`
- TO: `### Requirement: 新名称`
""",
    )
    _write(
        root / "openspec" / "specs" / "sample-capability" / "spec.md",
        """## Requirements

### Requirement: 新要求

#### Scenario: 新场景
- **WHEN** 新增
- **THEN** 存在

### Requirement: 已修改要求

#### Scenario: 修改后场景
- **WHEN** 修改
- **THEN** 更新

### Requirement: 新名称

#### Scenario: 重命名
- **WHEN** 查看
- **THEN** 存在
""",
    )

    assert audit_delta_sync(root, change) == ()


def test_delta_audit_rejects_unsynced_by_default_and_allows_explicit_override(
    tmp_path: Path,
) -> None:
    root = _create_repo(tmp_path)
    change = _create_change(root, "2026-08-23-unsynced-change", archived=True)
    _write(
        change / "specs" / "sample-capability" / "spec.md",
        """## ADDED Requirements

### Requirement: 尚未同步

#### Scenario: 尚未同步场景
- **WHEN** 归档
- **THEN** 拒绝
""",
    )

    with pytest.raises(SyncError, match="尚未同步"):
        audit_delta_sync(root, change)

    assert audit_delta_sync(root, change, allow_unsynced=True) == (
        "sample-capability: ADDED requirement 未同步：尚未同步",
    )


def test_delta_audit_rejects_archive_without_delta_specs(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    change = root / "openspec" / "changes" / "archive" / "2026-08-23-no-delta"
    _write(change / "proposal.md")

    with pytest.raises(SyncError, match="delta specs"):
        audit_delta_sync(root, change)


def test_include_audit_reports_missing_and_out_of_bounds_targets(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "active-change")
    sync_repository(root, "all", today=date(2026, 8, 23))
    page = root / "docs" / "changes" / "active" / "active-change" / "index.md"
    original = page.read_text(encoding="utf-8")

    page.write_text(original + "<!--@include: ./missing.md-->\n", encoding="utf-8")
    with pytest.raises(SyncError, match="missing.md"):
        audit_includes(root)

    page.write_text(original + "<!--@include: ../../../../../outside.md-->\n", encoding="utf-8")
    with pytest.raises(SyncError, match="允许范围"):
        audit_includes(root)


def test_include_and_count_audits_confirm_complete_projection(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "active-change")
    _create_change(root, "2026-08-22-archived-change", archived=True)
    expected = sync_repository(root, "all", today=date(2026, 8, 23))

    include_summary = audit_includes(root)
    count_summary = audit_counts(root)

    assert include_summary.pages == 7
    assert include_summary.targets == 11
    assert count_summary == expected


def test_count_audit_detects_missing_page_and_active_archive_duplicate(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "duplicate-change")
    _create_change(root, "2026-08-22-duplicate-change", archived=True)
    sync_repository(root, "all", today=date(2026, 8, 23))

    with pytest.raises(SyncError, match="active/archive 重复"):
        audit_counts(root)

    shutil_target = root / "openspec" / "changes" / "duplicate-change"
    for child in sorted(shutil_target.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    shutil_target.rmdir()
    archive_page = (
        root
        / "docs"
        / "changes"
        / "archive"
        / "2026-08-22-duplicate-change"
        / "index.md"
    )
    archive_page.unlink()
    with pytest.raises(SyncError, match="页面集合不一致"):
        audit_counts(root)


def test_cli_runs_active_sync_and_audits(tmp_path: Path) -> None:
    root = _create_repo(tmp_path)
    _create_change(root, "active-change")

    assert main(["active", "--root", str(root), "--date", "2026-08-23"]) == 0
    assert main(["audit-includes", "--root", str(root)]) == 0
    assert main(["audit-counts", "--root", str(root)]) == 0
