"""Deterministically project OpenSpec artifacts into the VitePress WIKI."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

ARCHIVE_NAME = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<name>.+)$")


class SyncError(RuntimeError):
    """Raised when the WIKI cannot be synchronized safely."""


@dataclass(frozen=True)
class SyncSummary:
    active_changes: tuple[str, ...]
    archived_changes: tuple[str, ...]
    main_specs: tuple[str, ...]


@dataclass(frozen=True)
class IncludeAuditSummary:
    pages: int
    targets: int


def validate_openspec_symlink(root: Path) -> None:
    link = root / "docs" / "openspec"
    expected = Path("../openspec")
    if link.is_symlink() and link.readlink() == expected:
        return
    raise SyncError(
        "docs/openspec 必须是指向 ../openspec 的相对符号链接。Windows 请先启用 "
        "Developer Mode，以管理员权限执行 `git config core.symlinks true` 后重新 checkout；"
        "不得复制 openspec 目录作为替代。"
    )


def _directories(path: Path) -> tuple[Path, ...]:
    if not path.is_dir():
        return ()
    return tuple(sorted((item for item in path.iterdir() if item.is_dir()), key=lambda p: p.name))


def _existing_created_date(page: Path) -> str | None:
    if not page.is_file():
        return None
    match = re.search(r"^createdDate: (?P<date>\d{4}-\d{2}-\d{2})$", page.read_text("utf-8"), re.MULTILINE)
    return match.group("date") if match else None


def _change_include_lines(page_dir: Path, source: Path, docs: Path) -> list[str]:
    artifacts: list[tuple[str, Path]] = []
    for title, filename in (("提案", "proposal.md"), ("设计", "design.md"), ("任务", "tasks.md")):
        path = source / filename
        if path.is_file():
            artifacts.append((title, path))
    for delta in sorted((source / "specs").glob("**/spec.md")):
        capability = delta.parent.relative_to(source / "specs").as_posix()
        artifacts.append((f"Delta Spec：{capability}", delta))

    lines: list[str] = []
    for title, artifact in artifacts:
        linked = docs / "openspec" / artifact.relative_to(docs.parent / "openspec")
        relative = Path(os.path.relpath(linked, page_dir)).as_posix()
        lines.extend((f"## {title}", "", f"<!--@include: {relative}-->", ""))
    return lines


def _render_change_page(
    *, docs: Path, source: Path, output: Path, title: str, status: str, created: str, archived: str | None
) -> None:
    frontmatter = ["---", f'title: "{title}"', f"status: {status}", f"createdDate: {created}"]
    if archived is not None:
        frontmatter.append(f"archivedDate: {archived}")
    frontmatter.extend(("---", ""))
    content = frontmatter + _change_include_lines(output.parent, source, docs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8")

    proposal = source / "proposal.md"
    if proposal.is_file():
        linked = docs / "openspec" / proposal.relative_to(docs.parent / "openspec")
        relative = Path(os.path.relpath(linked, output.parent)).as_posix()
        (output.parent / "proposal.md").write_text(
            "\n".join(
                (
                    "---",
                    f'title: "{title}：提案"',
                    "outline: false",
                    "---",
                    "",
                    f"<!--@include: {relative}-->",
                    "",
                )
            ),
            encoding="utf-8",
        )


def _render_spec_page(*, docs: Path, source: Path, output: Path, capability: str) -> None:
    linked = docs / "openspec" / source.relative_to(docs.parent / "openspec")
    relative = Path(os.path.relpath(linked, output.parent)).as_posix()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            (
                "---",
                f'title: "{capability}"',
                'status: "main-spec"',
                "---",
                "",
                f"# {capability}",
                "",
                f"<!--@include: {relative}-->",
                "",
            )
        ),
        encoding="utf-8",
    )


def _remove_stale(root: Path, expected: set[str]) -> None:
    if not root.is_dir():
        return
    for entry in _directories(root):
        if entry.name not in expected:
            shutil.rmtree(entry)


def _render_indexes_and_sidebar(
    docs: Path,
    active: tuple[str, ...],
    archived: tuple[str, ...],
    specs: tuple[str, ...],
) -> None:
    index = docs / "changes" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# OpenSpec WIKI", "", "## 进行中的变更", ""]
    lines.extend(f"- [{name}](./active/{name}/)" for name in active)
    if not active:
        lines.append("- 无")
    lines.extend(("", "## 已归档变更", ""))
    lines.extend(f"- [{name}](./archive/{name}/)" for name in archived)
    lines.extend(("", "## 主规格", ""))
    lines.extend(f"- [{name}](../specs/{name}/)" for name in specs)
    index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    specs_index = docs / "specs" / "index.md"
    specs_index.parent.mkdir(parents=True, exist_ok=True)
    spec_lines = ["# OpenSpec 主规格", ""]
    spec_lines.extend(f"- [{name}](./{name}/)" for name in specs)
    specs_index.write_text("\n".join(spec_lines).rstrip() + "\n", encoding="utf-8")

    sidebar = docs / ".vitepress" / "openspec-sidebar.generated.mts"
    sidebar.parent.mkdir(parents=True, exist_ok=True)
    groups = [
        {
            "text": "OpenSpec",
            "items": [{"text": "变更总览", "link": "/changes/"}],
        },
        {
            "text": "进行中的变更",
            "items": [{"text": name, "link": f"/changes/active/{name}/"} for name in active],
        },
        {
            "text": "已归档变更",
            "items": [{"text": name, "link": f"/changes/archive/{name}/"} for name in archived],
        },
        {
            "text": "主规格",
            "items": [{"text": name, "link": f"/specs/{name}/"} for name in specs],
        },
    ]
    sidebar.write_text(
        "// 此文件由 scripts/sync_wiki.py 生成，请勿手工编辑。\n"
        f"export const openspecSidebar = {json.dumps(groups, ensure_ascii=False, indent=2)};\n",
        encoding="utf-8",
    )


def _operation_sections(content: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$", content, re.MULTILINE)
    )
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group(1)] = content[match.end() : end]
    return sections


def _requirement_blocks(section: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    matches = list(re.finditer(r"^### Requirement: (?P<name>.+?)\s*$", section, re.MULTILINE))
    blocks: list[tuple[str, tuple[str, ...]]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        body = section[match.end() : end]
        scenarios = tuple(re.findall(r"^#### Scenario: (.+?)\s*$", body, re.MULTILINE))
        blocks.append((match.group("name").strip(), scenarios))
    return tuple(blocks)


def audit_delta_sync(
    root: Path, change: Path, *, allow_unsynced: bool = False
) -> tuple[str, ...]:
    delta_root = change / "specs"
    deltas = tuple(sorted(delta_root.glob("**/spec.md"))) if delta_root.is_dir() else ()
    if not deltas:
        raise SyncError(f"归档 change 缺少 delta specs：{change.name}")

    issues: list[str] = []
    for delta in deltas:
        capability = delta.parent.relative_to(delta_root).as_posix()
        main_path = root / "openspec" / "specs" / capability / "spec.md"
        main_content = main_path.read_text("utf-8") if main_path.is_file() else ""
        main_requirements = set(re.findall(r"^### Requirement: (.+?)\s*$", main_content, re.MULTILINE))
        main_scenarios = set(re.findall(r"^#### Scenario: (.+?)\s*$", main_content, re.MULTILINE))
        sections = _operation_sections(delta.read_text("utf-8"))

        for operation in ("ADDED", "MODIFIED"):
            for requirement, scenarios in _requirement_blocks(sections.get(operation, "")):
                if requirement not in main_requirements:
                    issues.append(
                        f"{capability}: {operation} requirement 未同步：{requirement}"
                    )
                    continue
                for scenario in scenarios:
                    if scenario not in main_scenarios:
                        issues.append(
                            f"{capability}: {operation} scenario 未同步：{scenario}"
                        )

        for requirement, _ in _requirement_blocks(sections.get("REMOVED", "")):
            if requirement in main_requirements:
                issues.append(f"{capability}: REMOVED requirement 仍存在：{requirement}")

        renamed = sections.get("RENAMED", "")
        from_names = re.findall(r"^- FROM: `### Requirement: (.+?)`\s*$", renamed, re.MULTILINE)
        to_names = re.findall(r"^- TO: `### Requirement: (.+?)`\s*$", renamed, re.MULTILINE)
        if len(from_names) != len(to_names):
            issues.append(f"{capability}: RENAMED FROM/TO 数量不一致")
        for old, new in zip(from_names, to_names, strict=False):
            if old in main_requirements or new not in main_requirements:
                issues.append(f"{capability}: RENAMED 未同步：{old} -> {new}")

    result = tuple(issues)
    if result and not allow_unsynced:
        raise SyncError("delta specs 尚未同步：\n- " + "\n- ".join(result))
    return result


def _generated_pages(root: Path) -> tuple[Path, ...]:
    docs = root / "docs"
    pages = [
        *sorted((docs / "changes").glob("*.md")),
        *sorted((docs / "changes" / "active").glob("**/*.md")),
        *sorted((docs / "changes" / "archive").glob("**/*.md")),
        *sorted((docs / "specs").glob("**/*.md")),
    ]
    return tuple(pages)


def audit_includes(root: Path) -> IncludeAuditSummary:
    root = root.resolve()
    validate_openspec_symlink(root)
    allowed = (root / "openspec").resolve()
    include_pattern = re.compile(r"<!--@include:\s*(.+?)-->")
    pages = _generated_pages(root)
    target_count = 0
    for page in pages:
        for raw_target in include_pattern.findall(page.read_text("utf-8")):
            target = (page.parent / raw_target.strip()).resolve()
            try:
                target.relative_to(allowed)
            except ValueError as exc:
                raise SyncError(f"include 目标超出允许范围：{page}: {raw_target}") from exc
            if not target.is_file():
                raise SyncError(f"include 目标不存在：{page}: {raw_target}")
            target_count += 1
    return IncludeAuditSummary(pages=len(pages), targets=target_count)


def _page_names(path: Path) -> set[str]:
    return {entry.parent.name for entry in path.glob("*/index.md")}


def audit_counts(root: Path) -> SyncSummary:
    root = root.resolve()
    changes = root / "openspec" / "changes"
    active = tuple(path.name for path in _directories(changes) if path.name != "archive")
    archived = tuple(path.name for path in _directories(changes / "archive"))
    specs = tuple(
        path.parent.relative_to(root / "openspec" / "specs").as_posix()
        for path in sorted((root / "openspec" / "specs").glob("**/spec.md"))
    )
    archived_bases = {
        match.group("name") for name in archived if (match := ARCHIVE_NAME.match(name)) is not None
    }
    duplicates = sorted(set(active) & archived_bases)
    if duplicates:
        raise SyncError("active/archive 重复：" + ", ".join(duplicates))

    docs = root / "docs"
    actual_active = _page_names(docs / "changes" / "active")
    actual_archived = _page_names(docs / "changes" / "archive")
    actual_specs = {
        path.parent.relative_to(docs / "specs").as_posix()
        for path in (docs / "specs").glob("**/index.md")
        if path.parent != docs / "specs"
    }
    expected_sets = (set(active), set(archived), set(specs))
    actual_sets = (actual_active, actual_archived, actual_specs)
    if actual_sets != expected_sets:
        labels = ("active", "archive", "specs")
        details = []
        for label, expected, actual in zip(labels, expected_sets, actual_sets, strict=True):
            if expected != actual:
                details.append(
                    f"{label} 缺失={sorted(expected - actual)} 额外={sorted(actual - expected)}"
                )
        raise SyncError("页面集合不一致：" + "; ".join(details))

    index = (docs / "changes" / "index.md").read_text("utf-8")
    sidebar = (docs / ".vitepress" / "openspec-sidebar.generated.mts").read_text("utf-8")
    index_labels = Counter(re.findall(r"^- \[(.+?)\]\(", index, re.MULTILINE))
    sidebar_labels = Counter(re.findall(r'^\s*"text": "(.+?)",?$', sidebar, re.MULTILINE))
    for name in (*active, *archived, *specs):
        if index_labels[name] != 1 or sidebar_labels[name] != 1:
            raise SyncError(f"索引或 Sidebar 计数不一致：{name}")
    return SyncSummary(active, archived, specs)


def _select_archives(archives: tuple[Path, ...], change: str | None) -> tuple[Path, ...]:
    if change is None:
        return archives
    selected = tuple(
        source
        for source in archives
        if source.name == change
        or ((match := ARCHIVE_NAME.match(source.name)) is not None and match.group("name") == change)
    )
    if not selected:
        raise SyncError(f"找不到归档 change：{change}")
    return selected


def sync_repository(
    root: Path,
    mode: str,
    *,
    today: date | None = None,
    change: str | None = None,
    allow_unsynced: bool = False,
) -> SyncSummary:
    if mode not in {"active", "archive", "all"}:
        raise SyncError(f"未知同步模式：{mode}")
    root = root.resolve()
    validate_openspec_symlink(root)
    docs = root / "docs"
    changes = root / "openspec" / "changes"
    active_sources = tuple(path for path in _directories(changes) if path.name != "archive")
    archive_sources = _directories(changes / "archive")
    spec_sources = tuple(sorted((root / "openspec" / "specs").glob("**/spec.md")))

    active_names = tuple(path.name for path in active_sources)
    archive_names = tuple(path.name for path in archive_sources)
    spec_names = tuple(path.parent.relative_to(root / "openspec" / "specs").as_posix() for path in spec_sources)
    current_date = (today or datetime.now(UTC).date()).isoformat()

    if mode in {"active", "all"}:
        active_root = docs / "changes" / "active"
        _remove_stale(active_root, set(active_names))
        for source in active_sources:
            output = active_root / source.name / "index.md"
            created = _existing_created_date(output) or current_date
            _render_change_page(
                docs=docs,
                source=source,
                output=output,
                title=source.name,
                status="active",
                created=created,
                archived=None,
            )

    if mode in {"archive", "all"}:
        selected_archives = _select_archives(archive_sources, change if mode == "archive" else None)
        if mode == "archive":
            for source in selected_archives:
                issues = audit_delta_sync(root, source, allow_unsynced=allow_unsynced)
                if issues:
                    print("警告：显式允许未同步 delta specs：\n- " + "\n- ".join(issues))
        archive_root = docs / "changes" / "archive"
        if mode == "all":
            _remove_stale(archive_root, set(archive_names))
        for source in selected_archives:
            match = ARCHIVE_NAME.match(source.name)
            if match is None:
                raise SyncError(f"归档目录缺少 YYYY-MM-DD 前缀：{source.name}")
            output = archive_root / source.name / "index.md"
            archived_date = match.group("date")
            _render_change_page(
                docs=docs,
                source=source,
                output=output,
                title=match.group("name"),
                status="archived",
                created=_existing_created_date(output) or archived_date,
                archived=archived_date,
            )
        active_root = docs / "changes" / "active"
        archived_bases = {ARCHIVE_NAME.match(name).group("name") for name in archive_names if ARCHIVE_NAME.match(name)}
        for entry in _directories(active_root):
            if entry.name in archived_bases and entry.name not in active_names:
                shutil.rmtree(entry)

    if mode in {"active", "archive", "all"}:
        specs_root = docs / "specs"
        _remove_stale(specs_root, set(spec_names))
        for source, capability in zip(spec_sources, spec_names, strict=True):
            _render_spec_page(
                docs=docs,
                source=source,
                output=specs_root / capability / "index.md",
                capability=capability,
            )

    _render_indexes_and_sidebar(docs, active_names, archive_names, spec_names)
    return SyncSummary(active_names, archive_names, spec_names)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("active", "archive", "all", "audit-includes", "audit-counts")
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--date", dest="run_date", type=date.fromisoformat)
    parser.add_argument("--change")
    parser.add_argument("--allow-unsynced", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.mode == "audit-includes":
            result = audit_includes(args.root)
            print(f"include audit: pages={result.pages}, targets={result.targets}")
        elif args.mode == "audit-counts":
            result = audit_counts(args.root)
            print(
                f"count audit: active={len(result.active_changes)}, "
                f"archive={len(result.archived_changes)}, specs={len(result.main_specs)}"
            )
        else:
            result = sync_repository(
                args.root,
                args.mode,
                today=args.run_date,
                change=args.change,
                allow_unsynced=args.allow_unsynced,
            )
            print(
                f"wiki sync: active={len(result.active_changes)}, "
                f"archive={len(result.archived_changes)}, specs={len(result.main_specs)}"
            )
    except SyncError as exc:
        print(f"wiki sync failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
