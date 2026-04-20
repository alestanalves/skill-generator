import os
from pathlib import Path

from skillforge.env import (
    ensure_openai_api_key,
    find_dotenv,
    load_dotenv,
    normalize_ollama_base_url,
    resolve_generation_model,
    resolve_model_provider,
    resolve_ollama_config,
)
from skillforge.models import ModelProviderKind


def test_find_dotenv_searches_parent_directories(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    (root / ".env").write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

    monkeypatch.chdir(nested)
    assert find_dotenv() == root / ".env"


def test_load_dotenv_populates_missing_env_var(tmp_path: Path, monkeypatch) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = load_dotenv(dotenv_path)

    assert loaded == dotenv_path
    assert os.environ["OPENAI_API_KEY"] == "sk-from-dotenv"


def test_load_dotenv_does_not_override_existing_env_var(tmp_path: Path, monkeypatch) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-shell")

    load_dotenv(dotenv_path)

    assert os.environ["OPENAI_API_KEY"] == "sk-from-shell"


def test_ensure_openai_api_key_reads_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    nested = root / "src"
    nested.mkdir(parents=True)
    (root / ".env").write_text("OPENAI_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(nested)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert ensure_openai_api_key() == "sk-from-dotenv"


def test_resolve_model_provider_defaults_to_openai(monkeypatch) -> None:
    monkeypatch.delenv("SKILL_GENERATOR_PROVIDER", raising=False)
    assert resolve_model_provider() is ModelProviderKind.OPENAI


def test_resolve_model_provider_reads_ollama(monkeypatch) -> None:
    monkeypatch.setenv("SKILL_GENERATOR_PROVIDER", "ollama")
    assert resolve_model_provider() is ModelProviderKind.OLLAMA


def test_normalize_ollama_base_url_appends_v1() -> None:
    assert normalize_ollama_base_url("http://localhost:11434") == "http://localhost:11434/v1/"
    assert normalize_ollama_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1/"


def test_resolve_generation_model_uses_ollama_model(monkeypatch) -> None:
    monkeypatch.delenv("SKILL_GENERATOR_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
    assert (
        resolve_generation_model(ModelProviderKind.OLLAMA)
        == "qwen2.5:14b-instruct"
    )


def test_resolve_ollama_config_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    base_url, api_key = resolve_ollama_config()
    assert base_url == "http://localhost:11434/v1/"
    assert api_key == "ollama"
