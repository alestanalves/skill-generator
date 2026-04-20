from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from typer import Context

from skillforge import __version__
from skillforge.env import resolve_generation_model, resolve_model_provider
from skillforge.generator import SkillForge
from skillforge.install import install_skill
from skillforge.layouts import write_skill_project
from skillforge.models import (
    GenerationConfig,
    InstallMode,
    ModelProviderKind,
    RequestedTarget,
    ValidationSeverity,
    VariantTarget,
)
from skillforge.validators import detect_skill_roots, validate_skill_directory

app = typer.Typer(
    invoke_without_command=True,
    help="Generate, validate, and install skills.",
)
console = Console()

INTERACTIVE_PROVIDERS = {
    "1": ModelProviderKind.OPENAI,
    "2": ModelProviderKind.OLLAMA,
    "openai": ModelProviderKind.OPENAI,
    "ollama": ModelProviderKind.OLLAMA,
}

INTERACTIVE_TARGETS = {
    "1": RequestedTarget.CODEX,
    "2": RequestedTarget.CLAUDE,
    "3": RequestedTarget.UNIVERSAL,
    "codex": RequestedTarget.CODEX,
    "claude": RequestedTarget.CLAUDE,
    "claude code": RequestedTarget.CLAUDE,
    "geral": RequestedTarget.UNIVERSAL,
    "universal": RequestedTarget.UNIVERSAL,
}


def _resolve_brief(brief: str | None, brief_file: Path | None) -> str:
    if brief and brief_file:
        raise typer.BadParameter("Use either a positional brief or --brief-file, not both.")
    if brief_file:
        return brief_file.expanduser().read_text(encoding="utf-8").strip()
    if brief:
        return brief.strip()
    raise typer.BadParameter("Provide a skill brief or use --brief-file.")


def _print_issues(title: str, issues) -> None:
    if not issues:
        return
    table = Table(title=title)
    table.add_column("Severity")
    table.add_column("Path")
    table.add_column("Message")
    for issue in issues:
        severity = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
        message = getattr(issue, "message", None)
        if message is None:
            title_text = getattr(issue, "title", "").strip()
            details_text = getattr(issue, "details", "").strip()
            message = f"{title_text}: {details_text}" if title_text else details_text
        table.add_row(severity, issue.relative_path or "-", message)
    console.print(table)


def _run_generation(config: GenerationConfig) -> None:
    config.progress_callback = config.progress_callback or (
        lambda message: console.print(f"[cyan]{message}[/cyan]")
    )
    forge = SkillForge(model=config.model, reasoning_effort=config.reasoning_effort)
    try:
        outcome = forge.generate(config)
    except KeyboardInterrupt:
        console.print("[yellow]Geração cancelada pelo usuário.[/yellow]")
        raise typer.Exit(code=130)
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Erro durante a geração:[/red] {exc}")
        raise typer.Exit(code=1)

    plan_table = Table(title="Generation Plan")
    plan_table.add_column("Field")
    plan_table.add_column("Value")
    plan_table.add_row("Skill name", outcome.plan.skill_name)
    plan_table.add_row("Targets", ", ".join(outcome.plan.requested_variants))
    plan_table.add_row("Summary", outcome.plan.summary)
    plan_table.add_row("Trigger strategy", outcome.plan.trigger_strategy)
    console.print(plan_table)

    if outcome.review is not None:
        review_table = Table(title="Review")
        review_table.add_column("Approved")
        review_table.add_column("Summary")
        review_table.add_row(str(outcome.review.approved), outcome.review.summary)
        console.print(review_table)
        _print_issues("Review Issues", outcome.review.issues)

    _print_issues("Validation Issues", outcome.validation_issues)
    errors = [
        issue
        for issue in outcome.validation_issues
        if issue.severity is ValidationSeverity.ERROR
    ]
    if errors:
        raise typer.Exit(code=1)

    written_files = write_skill_project(outcome.project, config.output_dir, config.target)
    file_table = Table(title="Written Files")
    file_table.add_column("Path")
    for path in written_files:
        file_table.add_row(str(path))
    console.print(file_table)


def _prompt_interactive_provider() -> ModelProviderKind:
    console.print("Qual provedor de modelo você quer usar?")
    console.print("1. OpenAI")
    console.print("2. Ollama")

    default_provider = resolve_model_provider()

    while True:
        default_label = "1" if default_provider is ModelProviderKind.OPENAI else "2"
        choice = typer.prompt("Escolha", default=default_label).strip().lower()
        provider = INTERACTIVE_PROVIDERS.get(choice)
        if provider is not None:
            return provider
        console.print("Escolha inválida. Use `1`, `2`, `openai` ou `ollama`.")


def _prompt_interactive_target() -> RequestedTarget:
    console.print("Para qual ferramenta você quer gerar a skill?")
    console.print("1. Codex")
    console.print("2. Claude Code")
    console.print("3. Geral")

    while True:
        choice = typer.prompt("Escolha", default="1").strip().lower()
        target = INTERACTIVE_TARGETS.get(choice)
        if target is not None:
            return target
        console.print(
            "Escolha inválida. Use `1`, `2`, `3`, `codex`, `claude code` ou `geral`."
        )


def _prompt_interactive_brief() -> str:
    while True:
        brief = typer.prompt("O que você quer gerar").strip()
        if brief:
            return brief
        console.print("A descrição não pode ficar vazia.")


def _prompt_interactive_model(provider: ModelProviderKind) -> str:
    try:
        return resolve_generation_model(provider)
    except RuntimeError:
        if provider is ModelProviderKind.OLLAMA:
            while True:
                model = typer.prompt("Qual modelo do Ollama você quer usar").strip()
                if model:
                    return model
                console.print("O nome do modelo não pode ficar vazio.")
        raise


@app.callback()
def main_callback(ctx: Context) -> None:
    if ctx.invoked_subcommand is not None:
        return

    provider = _prompt_interactive_provider()
    target = _prompt_interactive_target()
    brief = _prompt_interactive_brief()
    model = _prompt_interactive_model(provider)

    config = GenerationConfig(
        brief=brief,
        target=target,
        output_dir=Path("build/skill-generator").expanduser(),
        model=model,
        provider=provider,
        reasoning_effort="medium",
    )
    _run_generation(config)


@app.command()
def version() -> None:
    console.print(__version__)


@app.command()
def generate(
    brief: Annotated[str | None, typer.Argument(help="What the skill should do.")] = None,
    brief_file: Annotated[
        Path | None, typer.Option("--brief-file", help="Read the brief from a file.")
    ] = None,
    target: Annotated[
        RequestedTarget, typer.Option("--target", case_sensitive=False)
    ] = RequestedTarget.BOTH,
    output: Annotated[
        Path, typer.Option("--output", help="Directory where the generated bundle is written.")
    ] = Path("build/skill-generator"),
    name: Annotated[
        str | None, typer.Option("--name", help="Optional preferred kebab-case skill name.")
    ] = None,
    context_file: Annotated[
        list[Path] | None,
        typer.Option("--context-file", help="Additional text files to feed into generation."),
    ] = None,
    example_request: Annotated[
        list[str] | None,
        typer.Option("--example-request", help="Example prompts that should trigger the skill."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Model to use for generation.",
            envvar="SKILL_GENERATOR_MODEL",
        ),
    ] = None,
    provider: Annotated[
        ModelProviderKind | None,
        typer.Option(
            "--provider",
            help="Model provider to use for generation.",
            case_sensitive=False,
            envvar="SKILL_GENERATOR_PROVIDER",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Override the model base URL. Useful for Ollama.",
            envvar="OLLAMA_BASE_URL",
        ),
    ] = None,
    effort: Annotated[
        str, typer.Option("--effort", help="Reasoning effort for the model.")
    ] = "medium",
    skip_review: Annotated[
        bool, typer.Option("--skip-review", help="Skip the reviewer and repair pass.")
    ] = False,
    max_context_chars: Annotated[
        int,
        typer.Option(
            "--max-context-chars",
            help="Maximum characters loaded from each context file.",
        ),
    ] = 6000,
) -> None:
    resolved_brief = _resolve_brief(brief, brief_file)
    resolved_provider = resolve_model_provider(provider)
    resolved_model = resolve_generation_model(resolved_provider, model)
    config = GenerationConfig(
        brief=resolved_brief,
        target=target,
        output_dir=output.expanduser(),
        model=resolved_model,
        provider=resolved_provider,
        reasoning_effort=effort,
        preferred_name=name,
        context_files=list(context_file or []),
        example_requests=list(example_request or []),
        skip_review=skip_review,
        max_context_chars=max_context_chars,
        base_url=base_url,
    )
    _run_generation(config)


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Skill directory or generated bundle root.")],
    target: Annotated[
        VariantTarget | None,
        typer.Option("--target", case_sensitive=False, help="Limit validation to one target."),
    ] = None,
) -> None:
    roots = detect_skill_roots(path, target=target)
    if not roots:
        raise typer.BadParameter(f"No skills found under {path}.")

    all_issues = []
    for inferred_target, skill_root in roots:
        issues = validate_skill_directory(skill_root, inferred_target)
        all_issues.extend(issues)
        console.print(f"[bold]{inferred_target.value}[/bold] {skill_root}")

    _print_issues("Validation Issues", all_issues)
    if any(issue.severity is ValidationSeverity.ERROR for issue in all_issues):
        raise typer.Exit(code=1)


@app.command()
def install(
    source: Annotated[Path, typer.Argument(help="Generated bundle root or skill directory.")],
    target: Annotated[VariantTarget, typer.Option("--target", case_sensitive=False)],
    mode: Annotated[InstallMode, typer.Option("--mode", case_sensitive=False)] = InstallMode.COPY,
    destination_root: Annotated[
        Path | None,
        typer.Option("--destination-root", help="Override the default user skill directory."),
    ] = None,
    skill_name: Annotated[
        str | None,
        typer.Option("--skill-name", help="Pick one skill when the source contains many."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing install.")] = False,
) -> None:
    installed = install_skill(
        source=source,
        target=target,
        mode=mode,
        destination_root=destination_root,
        skill_name=skill_name,
        force=force,
    )
    console.print(str(installed))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
