from __future__ import annotations

import shutil
from pathlib import Path

from skillforge.models import InstallMode, VariantTarget
from skillforge.validators import detect_skill_roots


def default_install_root(target: VariantTarget) -> Path:
    if target is VariantTarget.CODEX:
        return Path.home() / ".agents" / "skills"
    if target is VariantTarget.CLAUDE:
        return Path.home() / ".claude" / "skills"
    raise ValueError("Universal skills do not have a single default install root.")


def resolve_install_source(
    source: Path, target: VariantTarget, skill_name: str | None = None
) -> Path:
    roots = detect_skill_roots(source, target=target)
    if skill_name is not None:
        roots = [entry for entry in roots if entry[1].name == skill_name]

    if not roots:
        raise ValueError(f"No {target.value} skill found under {source}.")
    if len(roots) > 1:
        names = ", ".join(root.name for _, root in roots)
        raise ValueError(
            f"More than one {target.value} skill was found ({names}). Pass --skill-name."
        )
    return roots[0][1]


def install_skill(
    source: Path,
    target: VariantTarget,
    mode: InstallMode,
    destination_root: Path | None = None,
    skill_name: str | None = None,
    force: bool = False,
) -> Path:
    source_root = resolve_install_source(source, target=target, skill_name=skill_name)
    install_root = (destination_root or default_install_root(target)).expanduser()
    install_root.mkdir(parents=True, exist_ok=True)

    destination = install_root / source_root.name
    if destination.exists() or destination.is_symlink():
        if not force:
            raise ValueError(f"Destination already exists: {destination}")
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)

    if mode is InstallMode.COPY:
        shutil.copytree(source_root, destination)
    else:
        destination.symlink_to(source_root, target_is_directory=True)

    return destination

