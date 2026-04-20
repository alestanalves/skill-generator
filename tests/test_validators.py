from skillforge.models import SkillFile, ValidationSeverity, VariantTarget
from skillforge.validators import split_frontmatter, validate_skill_files


def test_split_frontmatter_parses_yaml_and_body() -> None:
    frontmatter, body = split_frontmatter(
        "---\nname: test-skill\ndescription: Example skill.\n---\n# Body\n"
    )
    assert frontmatter["name"] == "test-skill"
    assert "Body" in body


def test_validate_skill_files_accepts_valid_codex_skill() -> None:
    issues = validate_skill_files(
        "ci-debugger",
        [
            SkillFile(
                relative_path="SKILL.md",
                purpose="skill",
                content=(
                    "---\n"
                    "name: ci-debugger\n"
                    "description: Investigate CI failures and propose fixes.\n"
                    "---\n"
                    "# CI Debugger\n\n"
                    "Use `scripts/check.sh` when logs need triage.\n"
                ),
            ),
            SkillFile(
                relative_path="scripts/check.sh",
                purpose="helper",
                content="#!/usr/bin/env bash\necho ok\n",
                executable=True,
            ),
            SkillFile(
                relative_path="agents/openai.yaml",
                purpose="codex metadata",
                content=(
                    "interface:\n"
                    "  display_name: CI Debugger\n"
                    "  short_description: Diagnose CI failures\n"
                    "policy:\n"
                    "  allow_implicit_invocation: true\n"
                ),
            ),
        ],
        VariantTarget.CODEX,
    )
    assert not [issue for issue in issues if issue.severity is ValidationSeverity.ERROR]


def test_validate_skill_files_flags_name_and_missing_reference() -> None:
    issues = validate_skill_files(
        "bad-skill",
        [
            SkillFile(
                relative_path="SKILL.md",
                purpose="skill",
                content=(
                    "---\n"
                    "name: BadSkill\n"
                    "description: Helps.\n"
                    "---\n"
                    "See [guide](references/GUIDE.md).\n"
                ),
            )
        ],
        VariantTarget.UNIVERSAL,
    )
    messages = [issue.message for issue in issues]
    assert any("lowercase kebab-case" in message for message in messages)
    assert any("Referenced file does not exist" in message for message in messages)

