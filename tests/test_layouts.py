from pathlib import Path

from skillforge.layouts import variant_root
from skillforge.models import RequestedTarget, VariantTarget
from skillforge.validators import detect_skill_roots


def test_variant_root_uses_wrappers_for_both_targets(tmp_path: Path) -> None:
    codex_root = variant_root(
        tmp_path, RequestedTarget.BOTH, "triage-logs", VariantTarget.CODEX
    )
    claude_root = variant_root(
        tmp_path, RequestedTarget.BOTH, "triage-logs", VariantTarget.CLAUDE
    )
    assert codex_root == tmp_path / "codex" / ".agents" / "skills" / "triage-logs"
    assert claude_root == tmp_path / "claude" / ".claude" / "skills" / "triage-logs"


def test_detect_skill_roots_finds_nested_generated_skills(tmp_path: Path) -> None:
    codex_skill = tmp_path / "codex" / ".agents" / "skills" / "triage-logs"
    claude_skill = tmp_path / "claude" / ".claude" / "skills" / "triage-logs"
    codex_skill.mkdir(parents=True)
    claude_skill.mkdir(parents=True)
    (codex_skill / "SKILL.md").write_text("---\nname: triage-logs\ndescription: x\n---\nBody\n")
    (claude_skill / "SKILL.md").write_text("---\nname: triage-logs\ndescription: x\n---\nBody\n")

    roots = detect_skill_roots(tmp_path)
    detected = {(target.value, path.name) for target, path in roots}
    assert ("codex", "triage-logs") in detected
    assert ("claude", "triage-logs") in detected
