from pathlib import Path

from typer.testing import CliRunner

from rich.console import Console

from skillforge.cli import _GenerationFeedback, _print_issues, _run_generation, app
from skillforge.models import (
    GenerationConfig,
    GenerationOutcome,
    ModelProviderKind,
    RequestedTarget,
    ReviewIssue,
    SkillPlan,
    SkillProject,
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


def test_generation_feedback_uses_spinner_when_stdout_supports_live_updates(monkeypatch) -> None:
    updates = []
    captured = {}

    class FakeProgress:
        def __init__(self, *args, **kwargs) -> None:
            captured["kwargs"] = kwargs

        def __enter__(self):
            captured["entered"] = True
            return self

        def __exit__(self, exc_type, exc, exc_tb):
            captured["exited"] = True
            return False

        def add_task(self, description: str, total=None):
            captured["description"] = description
            captured["total"] = total
            return 7

        def update(self, task_id: int, description: str) -> None:
            updates.append((task_id, description))

    monkeypatch.setattr("skillforge.cli._supports_live_progress", lambda: True)
    monkeypatch.setattr("skillforge.cli.Progress", FakeProgress)

    with _GenerationFeedback(output_console=Console()) as feedback:
        feedback.update("Planejando a skill...")

    assert captured["entered"] is True
    assert captured["exited"] is True
    assert captured["description"] == "Iniciando geração..."
    assert captured["total"] is None
    assert updates == [(7, "Planejando a skill...")]


def test_run_generation_preserves_custom_progress_callback(monkeypatch) -> None:
    progress_messages = []

    def custom_progress(message: str) -> None:
        progress_messages.append(message)

    def fake_generate(self, config: GenerationConfig) -> GenerationOutcome:
        assert config.progress_callback is not None
        config.progress_callback("Planejando a skill...")
        return GenerationOutcome(
            plan=SkillPlan(
                skill_name="review-skill",
                requested_variants=["codex"],
                summary="Resumo",
                trigger_strategy="Sempre que o usuário pedir revisão.",
            ),
            project=SkillProject(
                skill_name="review-skill",
                summary="Resumo",
                trigger_description="Detecta pedidos de revisão.",
                variants=[],
            ),
            review=None,
            validation_issues=[],
        )

    monkeypatch.setattr("skillforge.cli._supports_live_progress", lambda: False)
    monkeypatch.setattr("skillforge.cli.SkillForge.generate", fake_generate)
    monkeypatch.setattr("skillforge.cli.write_skill_project", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("skillforge.cli.console.print", lambda *_args, **_kwargs: None)

    config = GenerationConfig(
        brief="Criar skill",
        target=RequestedTarget.CODEX,
        output_dir=Path("build/skill-generator"),
        model="gpt-5.3-codex",
        progress_callback=custom_progress,
    )

    _run_generation(config)

    assert progress_messages == ["Planejando a skill..."]
    assert config.progress_callback is custom_progress


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
