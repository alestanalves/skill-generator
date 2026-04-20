from __future__ import annotations

from pathlib import Path

from agents import Agent, ModelSettings, OpenAIProvider, RunConfig, Runner
from agents.models.interface import Model
from openai.types.shared.reasoning import Reasoning

from skillforge.env import ensure_openai_api_key, resolve_ollama_config
from skillforge.models import (
    ContextSnippet,
    GenerationConfig,
    GenerationOutcome,
    ModelProviderKind,
    ReviewReport,
    SkillPlan,
    SkillProject,
    ValidationSeverity,
    ValidationIssue,
    VariantTarget,
)
from skillforge.prompts import (
    AUTHOR_SYSTEM_PROMPT,
    PLAN_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    build_author_prompt,
    build_generation_prompt,
    build_repair_prompt,
    build_review_prompt,
)
from skillforge.validators import validate_skill_files


class SkillForge:
    def __init__(self, model: str, reasoning_effort: str = "medium") -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort

    def generate(self, config: GenerationConfig) -> GenerationOutcome:
        self._ensure_api_key(config)
        self._notify(config, "Carregando contexto...")
        context_snippets = self._load_context_snippets(
            config.context_files, max_chars=config.max_context_chars
        )

        self._notify(config, "Planejando a skill...")
        plan = self._run_plan_agent(config, context_snippets)
        self._notify(config, "Gerando os arquivos da skill...")
        project = self._run_author_agent(config, plan, context_snippets)
        self._notify(config, "Validando a estrutura gerada...")
        validation_issues = self._validate_project(
            project,
            expected_skill_name=plan.skill_name,
            expected_targets=config.target.variants(),
        )

        review: ReviewReport | None = None
        if not config.skip_review:
            self._notify(config, "Revisando a qualidade da skill...")
            review = self._run_review_agent(config, plan, project, validation_issues)
            if any(issue.severity == "blocking" for issue in review.issues):
                self._notify(config, "Corrigindo problemas encontrados na revisão...")
                project = self._run_repair_agent(
                    config, plan, project, review, validation_issues
                )
                self._notify(config, "Revalidando após correções...")
                validation_issues = self._validate_project(
                    project,
                    expected_skill_name=plan.skill_name,
                    expected_targets=config.target.variants(),
                )

        return GenerationOutcome(
            plan=plan,
            project=project,
            review=review,
            validation_issues=validation_issues,
        )

    def _run_plan_agent(
        self, config: GenerationConfig, context_snippets: list[ContextSnippet]
    ) -> SkillPlan:
        model, run_config = self._resolve_model_runtime(config)
        agent = Agent(
            name="Skill Planner",
            instructions=PLAN_SYSTEM_PROMPT,
            model=model,
            model_settings=self._model_settings(),
            output_type=SkillPlan,
        )
        result = Runner.run_sync(
            agent,
            build_generation_prompt(config, context_snippets),
            max_turns=1,
            run_config=run_config,
        )
        return result.final_output_as(SkillPlan, raise_if_incorrect_type=True)

    def _run_author_agent(
        self,
        config: GenerationConfig,
        plan: SkillPlan,
        context_snippets: list[ContextSnippet],
    ) -> SkillProject:
        model, run_config = self._resolve_model_runtime(config)
        agent = Agent(
            name="Skill Author",
            instructions=AUTHOR_SYSTEM_PROMPT,
            model=model,
            model_settings=self._model_settings(),
            output_type=SkillProject,
        )
        result = Runner.run_sync(
            agent,
            build_author_prompt(config, plan, context_snippets),
            max_turns=1,
            run_config=run_config,
        )
        return result.final_output_as(SkillProject, raise_if_incorrect_type=True)

    def _run_review_agent(
        self,
        config: GenerationConfig,
        plan: SkillPlan,
        project: SkillProject,
        validation_issues,
    ) -> ReviewReport:
        model, run_config = self._resolve_model_runtime(config)
        agent = Agent(
            name="Skill Reviewer",
            instructions=REVIEW_SYSTEM_PROMPT,
            model=model,
            model_settings=self._model_settings(),
            output_type=ReviewReport,
        )
        result = Runner.run_sync(
            agent,
            build_review_prompt(
                config,
                plan,
                project,
                local_validation=[self._format_issue(issue) for issue in validation_issues],
            ),
            max_turns=1,
            run_config=run_config,
        )
        return result.final_output_as(ReviewReport, raise_if_incorrect_type=True)

    def _run_repair_agent(
        self,
        config: GenerationConfig,
        plan: SkillPlan,
        project: SkillProject,
        review: ReviewReport,
        validation_issues,
    ) -> SkillProject:
        model, run_config = self._resolve_model_runtime(config)
        agent = Agent(
            name="Skill Repairer",
            instructions=AUTHOR_SYSTEM_PROMPT,
            model=model,
            model_settings=self._model_settings(),
            output_type=SkillProject,
        )
        result = Runner.run_sync(
            agent,
            build_repair_prompt(
                config,
                plan,
                project,
                review,
                local_validation=[self._format_issue(issue) for issue in validation_issues],
            ),
            max_turns=1,
            run_config=run_config,
        )
        return result.final_output_as(SkillProject, raise_if_incorrect_type=True)

    def _validate_project(
        self,
        project: SkillProject,
        expected_skill_name: str,
        expected_targets: list[VariantTarget],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if project.skill_name != expected_skill_name:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="Project skill_name does not match the approved plan.",
                )
            )
        actual_targets = [VariantTarget(variant.target) for variant in project.variants]
        if sorted(target.value for target in actual_targets) != sorted(
            target.value for target in expected_targets
        ):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Generated variants do not match the requested target. "
                        f"Expected {[target.value for target in expected_targets]}, "
                        f"got {[target.value for target in actual_targets]}."
                    ),
                )
            )
        for variant in project.variants:
            issues.extend(
                validate_skill_files(
                    skill_dir_name=project.skill_name,
                    files=variant.files,
                    target=VariantTarget(variant.target),
                )
            )
        return issues

    def _load_context_snippets(
        self, context_files: list[Path], max_chars: int
    ) -> list[ContextSnippet]:
        snippets: list[ContextSnippet] = []
        for path in context_files:
            resolved = path.expanduser().resolve()
            content = resolved.read_text(encoding="utf-8")
            trimmed = content[:max_chars]
            if len(content) > max_chars:
                trimmed += "\n\n[truncated]"
            snippets.append(ContextSnippet(path=str(resolved), content=trimmed))
        return snippets

    def _model_settings(self) -> ModelSettings:
        return ModelSettings(
            reasoning=Reasoning(effort=self.reasoning_effort),
        )

    def _resolve_model_runtime(
        self, config: GenerationConfig
    ) -> tuple[str | Model, RunConfig | None]:
        if config.provider is ModelProviderKind.OLLAMA:
            base_url, api_key = resolve_ollama_config(config.base_url)
            provider = OpenAIProvider(
                api_key=api_key,
                base_url=base_url,
                use_responses=False,
            )
            return provider.get_model(config.model), RunConfig(tracing_disabled=True)

        return self.model, None

    @staticmethod
    def _notify(config: GenerationConfig, message: str) -> None:
        if config.progress_callback is not None:
            config.progress_callback(message)

    @staticmethod
    def _format_issue(issue) -> str:
        location = issue.relative_path or "project"
        return f"{issue.severity.value.upper()} {location}: {issue.message}"

    @staticmethod
    def _ensure_api_key(config: GenerationConfig | None = None) -> None:
        if config is not None and config.provider is ModelProviderKind.OLLAMA:
            resolve_ollama_config(config.base_url)
            return
        ensure_openai_api_key()
