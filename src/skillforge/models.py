from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class VariantTarget(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"
    UNIVERSAL = "universal"


class RequestedTarget(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"
    BOTH = "both"
    UNIVERSAL = "universal"

    def variants(self) -> list[VariantTarget]:
        if self is RequestedTarget.BOTH:
            return [VariantTarget.CODEX, VariantTarget.CLAUDE]
        if self is RequestedTarget.CODEX:
            return [VariantTarget.CODEX]
        if self is RequestedTarget.CLAUDE:
            return [VariantTarget.CLAUDE]
        return [VariantTarget.UNIVERSAL]


class InstallMode(str, Enum):
    COPY = "copy"
    SYMLINK = "symlink"


class ModelProviderKind(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ContextSnippet(BaseModel):
    path: str = Field(description="Source path for this context snippet.")
    content: str = Field(description="Trimmed plain-text content loaded from disk.")


class SkillPlan(BaseModel):
    skill_name: str = Field(description="kebab-case skill folder name, 1-64 chars.")
    requested_variants: list[Literal["codex", "claude", "universal"]] = Field(
        description="Target variants that must be produced."
    )
    summary: str = Field(description="Short summary of the skill's purpose.")
    trigger_strategy: str = Field(
        description="How the description and frontmatter should trigger the skill."
    )
    structure_decisions: list[str] = Field(
        default_factory=list,
        description="Key authoring decisions, including scripts, references, or assets.",
    )
    authoring_notes: list[str] = Field(
        default_factory=list,
        description="Notes the author should follow when generating files.",
    )


class SkillFile(BaseModel):
    relative_path: str = Field(
        description="Path relative to the skill root, e.g. SKILL.md or scripts/check.sh."
    )
    purpose: str = Field(description="Why this file exists.")
    content: str = Field(description="Full file contents.")
    executable: bool = Field(
        default=False, description="Set true when the file should be marked executable."
    )


class SkillVariant(BaseModel):
    target: Literal["codex", "claude", "universal"]
    summary: str = Field(description="What is specialized for this target.")
    files: list[SkillFile] = Field(description="Files for the skill root.")


class SkillProject(BaseModel):
    skill_name: str = Field(description="Canonical skill name shared across variants.")
    summary: str = Field(description="High-level summary of the generated skill.")
    trigger_description: str = Field(
        description="The intended trigger behavior across variants."
    )
    install_notes: list[str] = Field(
        default_factory=list,
        description="Short notes for the user after generation.",
    )
    variants: list[SkillVariant] = Field(description="Generated target variants.")


class ReviewIssue(BaseModel):
    severity: Literal["blocking", "major", "minor"]
    title: str
    details: str
    target: str | None = None
    relative_path: str | None = None


class ReviewReport(BaseModel):
    approved: bool
    summary: str
    issues: list[ReviewIssue] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    severity: ValidationSeverity
    message: str
    relative_path: str | None = None


@dataclass(slots=True)
class GenerationConfig:
    brief: str
    target: RequestedTarget
    output_dir: Path
    model: str
    provider: ModelProviderKind = ModelProviderKind.OPENAI
    reasoning_effort: str = "medium"
    preferred_name: str | None = None
    context_files: list[Path] = field(default_factory=list)
    example_requests: list[str] = field(default_factory=list)
    skip_review: bool = False
    max_context_chars: int = 6000
    progress_callback: Callable[[str], None] | None = None
    base_url: str | None = None


@dataclass(slots=True)
class GenerationOutcome:
    plan: SkillPlan
    project: SkillProject
    review: ReviewReport | None
    validation_issues: list[ValidationIssue]
    written_files: list[Path] = field(default_factory=list)
