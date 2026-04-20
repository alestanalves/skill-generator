from __future__ import annotations

from pathlib import Path

from skillforge.models import RequestedTarget, SkillProject, VariantTarget


def variant_root(
    output_dir: Path,
    requested_target: RequestedTarget,
    skill_name: str,
    variant_target: VariantTarget,
) -> Path:
    if requested_target is RequestedTarget.BOTH:
        if variant_target is VariantTarget.CODEX:
            return output_dir / "codex" / ".agents" / "skills" / skill_name
        if variant_target is VariantTarget.CLAUDE:
            return output_dir / "claude" / ".claude" / "skills" / skill_name
        return output_dir / "universal" / skill_name

    if variant_target is VariantTarget.CODEX:
        return output_dir / ".agents" / "skills" / skill_name
    if variant_target is VariantTarget.CLAUDE:
        return output_dir / ".claude" / "skills" / skill_name
    return output_dir / skill_name


def write_skill_project(
    project: SkillProject, output_dir: Path, requested_target: RequestedTarget
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: list[Path] = []

    for variant in project.variants:
        root = variant_root(
            output_dir=output_dir,
            requested_target=requested_target,
            skill_name=project.skill_name,
            variant_target=VariantTarget(variant.target),
        )
        for file in variant.files:
            destination = root / Path(file.relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = file.content if file.content.endswith("\n") else f"{file.content}\n"
            destination.write_text(content, encoding="utf-8")
            if file.executable:
                destination.chmod(destination.stat().st_mode | 0o111)
            written_files.append(destination)

    return written_files

