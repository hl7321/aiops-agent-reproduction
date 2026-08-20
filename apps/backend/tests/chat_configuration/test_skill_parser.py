import pytest

from super_ai.chat_configuration.parser import (
    SkillDocumentValidationError,
    normalize_skill_name,
    parse_skill_document,
)

VALID = (
    b"---\nname: Knowledge Search\ndescription:  Search knowledge safely.  \n"
    b"level: 1\n---\n\n# Steps\nUse retrieval.\n"
)


def test_parser_normalizes_and_preserves_valid_skill() -> None:
    parsed = parse_skill_document("SKILL.md", VALID)
    assert parsed.name == "knowledge-search"
    assert parsed.description == "Search knowledge safely."
    assert parsed.filename == "SKILL.md"
    assert parsed.content == VALID.decode()
    assert parsed.metadata == {
        "name": "Knowledge Search",
        "description": "Search knowledge safely.",
        "level": 1,
    }
    assert parsed.summary == "Search knowledge safely."


@pytest.mark.parametrize("filename", ["skill.md", "folder/SKILL.md", "SKILL.MD"])
def test_parser_rejects_non_exact_filename(filename: str) -> None:
    with pytest.raises(SkillDocumentValidationError):
        parse_skill_document(filename, VALID)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b"name: no-frontmatter",
        b"---\n- list\n---\nbody",
        b"---\nname: x\n---\nbody",
        b"---\nname: x\ndescription: y\ndate: 2026-08-18\n---\nbody",
    ],
)
def test_parser_rejects_unsafe_or_incomplete_documents(payload: bytes) -> None:
    with pytest.raises(SkillDocumentValidationError):
        parse_skill_document("SKILL.md", payload)


def test_parser_rejects_oversized_file() -> None:
    with pytest.raises(SkillDocumentValidationError):
        parse_skill_document("SKILL.md", b"x" * (262144 + 1))


def test_name_normalization_has_stable_boundary() -> None:
    assert normalize_skill_name(" API__Troubleshooting ") == "api-troubleshooting"
    with pytest.raises(SkillDocumentValidationError):
        normalize_skill_name("中文技能")
