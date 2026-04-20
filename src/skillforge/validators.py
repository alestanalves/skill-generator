from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Iterable

import yaml

from skillforge.models import SkillFile, ValidationIssue, ValidationSeverity, VariantTarget

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_RE = re.compile(r"(?:scripts|references|assets)/[A-Za-z0-9._/\-]+")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def split_frontmatter(content: str) -> tuple[dict, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter delimited by ---")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValueError("SKILL.md frontmatter is missing the closing --- delimiter")

    raw_yaml = "\n".join(lines[1:end_index])
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Frontmatter must parse to a YAML mapping")

    body = "\n".join(lines[end_index + 1 :]).strip()
    return data, body


def _normalize_relative_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute():
        raise ValueError("Skill files must use relative paths")
    if ".." in pure.parts:
        raise ValueError("Skill files must not escape the skill root")
    return pure.as_posix()


def _extract_referenced_paths(body: str) -> set[str]:
    references = set(REFERENCE_RE.findall(body))
    for match in MARKDOWN_LINK_RE.findall(body):
        if "://" in match or match.startswith("#"):
            continue
        if match.startswith("./"):
            match = match[2:]
        try:
            references.add(_normalize_relative_path(match))
        except ValueError:
            continue
    return {path for path in references if path.startswith(("scripts/", "references/", "assets/"))}


def validate_skill_files(
    skill_dir_name: str, files: Iterable[SkillFile], target: VariantTarget
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    file_map: dict[str, str] = {}

    for file in files:
        try:
            normalized = _normalize_relative_path(file.relative_path)
        except ValueError as exc:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path=file.relative_path,
                    message=str(exc),
                )
            )
            continue
        file_map[normalized] = file.content

    if "SKILL.md" not in file_map:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="Missing required SKILL.md file.",
            )
        )
        return issues

    try:
        frontmatter, body = split_frontmatter(file_map["SKILL.md"])
    except ValueError as exc:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message=str(exc),
            )
        )
        return issues

    name = frontmatter.get("name")
    description = frontmatter.get("description")

    if not isinstance(name, str) or not name:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="Frontmatter must include a non-empty string `name`.",
            )
        )
    else:
        if len(name) > 64:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path="SKILL.md",
                    message="Frontmatter `name` must be 64 characters or fewer.",
                )
            )
        if not NAME_RE.fullmatch(name):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path="SKILL.md",
                    message="Frontmatter `name` must be lowercase kebab-case.",
                )
            )
        if name != skill_dir_name:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path="SKILL.md",
                    message="Frontmatter `name` must match the parent directory name.",
                )
            )

    if not isinstance(description, str) or not description.strip():
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="Frontmatter must include a non-empty string `description`.",
            )
        )
    elif len(description) > 1024:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="Frontmatter `description` must be 1024 characters or fewer.",
            )
        )

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or len(compatibility) > 500
    ):
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="Optional `compatibility` must be a string up to 500 characters.",
            )
        )

    if not body.strip():
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                relative_path="SKILL.md",
                message="SKILL.md must contain markdown instructions after the frontmatter.",
            )
        )

    if len(file_map["SKILL.md"].splitlines()) > 500:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                relative_path="SKILL.md",
                message="SKILL.md exceeds 500 lines; consider moving detail into references.",
            )
        )

    for referenced_path in sorted(_extract_referenced_paths(body)):
        if referenced_path not in file_map:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    relative_path="SKILL.md",
                    message=f"Referenced file does not exist: {referenced_path}",
                )
            )

    if target is VariantTarget.CODEX:
        if "agents/openai.yaml" not in file_map:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    relative_path="agents/openai.yaml",
                    message="Codex variant does not include optional agents/openai.yaml metadata.",
                )
            )
        else:
            try:
                openai_yaml = yaml.safe_load(file_map["agents/openai.yaml"]) or {}
            except yaml.YAMLError as exc:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        relative_path="agents/openai.yaml",
                        message=f"Invalid YAML: {exc}",
                    )
                )
            else:
                if not isinstance(openai_yaml, dict):
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            relative_path="agents/openai.yaml",
                            message="agents/openai.yaml must be a YAML mapping.",
                        )
                    )
                policy = openai_yaml.get("policy")
                if policy is not None and not isinstance(policy, dict):
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            relative_path="agents/openai.yaml",
                            message="`policy` in agents/openai.yaml must be a mapping.",
                        )
                    )
                if isinstance(policy, dict):
                    implicit = policy.get("allow_implicit_invocation")
                    if implicit is not None and not isinstance(implicit, bool):
                        issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                relative_path="agents/openai.yaml",
                                message="`allow_implicit_invocation` must be a boolean.",
                            )
                        )

    if target is VariantTarget.CLAUDE:
        boolean_fields = ("disable-model-invocation", "user-invocable")
        for field_name in boolean_fields:
            field_value = frontmatter.get(field_name)
            if field_value is not None and not isinstance(field_value, bool):
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        relative_path="SKILL.md",
                        message=f"`{field_name}` must be a boolean when present.",
                    )
                )
        allowed_tools = frontmatter.get("allowed-tools")
        if allowed_tools is not None and not isinstance(allowed_tools, (str, list)):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path="SKILL.md",
                    message="`allowed-tools` must be a string or YAML list.",
                )
            )
        shell = frontmatter.get("shell")
        if shell is not None and shell not in {"bash", "powershell"}:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    relative_path="SKILL.md",
                    message="`shell` must be either `bash` or `powershell`.",
                )
            )

    return issues


def infer_target_from_path(path: Path) -> VariantTarget:
    parts = set(path.parts)
    if ".claude" in parts:
        return VariantTarget.CLAUDE
    if ".agents" in parts:
        return VariantTarget.CODEX
    return VariantTarget.UNIVERSAL


def validate_skill_directory(
    skill_dir: Path, target: VariantTarget | None = None
) -> list[ValidationIssue]:
    chosen_target = target or infer_target_from_path(skill_dir)
    files: list[SkillFile] = []
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(skill_dir).as_posix()
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = ""
        files.append(
            SkillFile(
                relative_path=relative_path,
                purpose="loaded-from-disk",
                content=content,
                executable=False,
            )
        )
    return validate_skill_files(skill_dir.name, files, chosen_target)


def detect_skill_roots(
    path: Path, target: VariantTarget | None = None
) -> list[tuple[VariantTarget, Path]]:
    path = path.expanduser().resolve()
    candidates: list[Path]

    if path.is_file() and path.name == "SKILL.md":
        candidates = [path.parent]
    elif path.is_dir() and (path / "SKILL.md").exists():
        candidates = [path]
    elif path.is_dir():
        candidates = [candidate.parent for candidate in path.rglob("SKILL.md")]
    else:
        candidates = []

    results: list[tuple[VariantTarget, Path]] = []
    for candidate in sorted(set(candidates)):
        inferred = infer_target_from_path(candidate)
        if target is not None and inferred is not target:
            continue
        results.append((inferred, candidate))
    return results
