from pathlib import Path

from super_ai.chat_configuration.parser import parse_skill_document

ROOT = Path(__file__).resolve().parents[4]
NAMES = {
    "knowledge-search",
    "log-analysis",
    "incident-report",
    "api-troubleshooting",
    "change-risk-review",
}


def test_five_examples_follow_production_upload_contract() -> None:
    parsed_names: set[str] = set()
    for name in NAMES:
        path = ROOT / "docs/examples/skills" / name / "SKILL.md"
        parsed = parse_skill_document(path.name, path.read_bytes())
        assert parsed.name == path.parent.name
        parsed_names.add(parsed.name)
    assert parsed_names == NAMES
