from pathlib import Path

from typer.testing import CliRunner

from skillforge.cli import _print_issues, app
from skillforge.models import (
    GenerationConfig,
    ModelProviderKind,
    RequestedTarget,
    ReviewIssue,
)

runner = CliRunner()


def test_interactive_root_flow(monkeypatch) -> None:
    captured: dict[str, GenerationConfig] = {}

    def fake_run_generation(config: GenerationConfig) -> None:
        captured["config"] = config

    monkeypatch.setattr("skillforge.cli._run_generation", fake_run_generation)
    monkeypatch.setattr("skillforge.cli.resolve_model_provider", lambda: ModelProviderKind.OPENAI)
    monkeypatch.setattr(
        "skillforge.cli.resolve_generation_model",
        lambda provider, explicit_model=None: "gpt-5.3-codex",
    )

    result = runner.invoke(app, input="1\n3\nCriar uma skill para revisar PRs\n")

    assert result.exit_code == 0
    assert captured["config"].provider is ModelProviderKind.OPENAI
    assert captured["config"].target is RequestedTarget.UNIVERSAL
    assert captured["config"].brief == "Criar uma skill para revisar PRs"
    assert captured["config"].output_dir == Path("build/skill-generator")


def test_generate_command_still_works(monkeypatch) -> None:
    captured: dict[str, GenerationConfig] = {}

    def fake_run_generation(config: GenerationConfig) -> None:
        captured["config"] = config

    monkeypatch.setattr("skillforge.cli._run_generation", fake_run_generation)
    monkeypatch.setattr(
        "skillforge.cli.resolve_generation_model",
        lambda provider, explicit_model=None: explicit_model or "gpt-5.3-codex",
    )

    result = runner.invoke(app, ["generate", "Criar skill", "--target", "codex"])

    assert result.exit_code == 0
    assert captured["config"].provider is ModelProviderKind.OPENAI
    assert captured["config"].target is RequestedTarget.CODEX
    assert captured["config"].brief == "Criar skill"


def test_generate_command_supports_ollama(monkeypatch) -> None:
    captured: dict[str, GenerationConfig] = {}

    def fake_run_generation(config: GenerationConfig) -> None:
        captured["config"] = config

    monkeypatch.setattr("skillforge.cli._run_generation", fake_run_generation)
    monkeypatch.setattr(
        "skillforge.cli.resolve_generation_model",
        lambda provider, explicit_model=None: explicit_model or "qwen2.5:14b-instruct",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "Criar skill",
            "--provider",
            "ollama",
            "--model",
            "qwen2.5:14b-instruct",
            "--base-url",
            "http://localhost:11434",
        ],
    )

    assert result.exit_code == 0
    assert captured["config"].provider is ModelProviderKind.OLLAMA
    assert captured["config"].model == "qwen2.5:14b-instruct"
    assert captured["config"].base_url == "http://localhost:11434"


def test_generate_command_reports_errors_cleanly(monkeypatch) -> None:
    def fake_generate(*_args, **_kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr("skillforge.cli.SkillForge.generate", fake_generate)

    result = runner.invoke(app, ["generate", "Criar skill", "--target", "codex"])

    assert result.exit_code == 1
    assert "Erro durante a geração:" in result.output
    assert "falha simulada" in result.output


def test_print_review_issues_works_with_string_severity(monkeypatch) -> None:
    issue = ReviewIssue(
        severity="major",
        title="Melhoria opcional",
        details="Adicionar agents/openai.yaml para melhor catálogo no Codex.",
        relative_path="agents/openai.yaml",
    )
    captured = {}

    def fake_print(table) -> None:
        captured["table"] = table

    monkeypatch.setattr("skillforge.cli.console.print", fake_print)

    _print_issues("Review Issues", [issue])

    assert captured["table"].title == "Review Issues"
