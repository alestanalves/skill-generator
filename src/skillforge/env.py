from __future__ import annotations

import os
from pathlib import Path

from skillforge.models import ModelProviderKind


def find_dotenv(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    search_roots = [current, *current.parents]

    for directory in search_roots:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: Path | None = None, *, override: bool = False) -> Path | None:
    dotenv_path = path or find_dotenv()
    if dotenv_path is None:
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value

    return dotenv_path


def ensure_openai_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Add it to the project root .env or export it in the shell."
        )
    return api_key


def resolve_model_provider(explicit: str | ModelProviderKind | None = None) -> ModelProviderKind:
    load_dotenv()
    raw = explicit.value if isinstance(explicit, ModelProviderKind) else explicit
    raw = (raw or os.environ.get("SKILL_GENERATOR_PROVIDER") or "openai").strip().lower()

    try:
        return ModelProviderKind(raw)
    except ValueError as exc:
        raise RuntimeError(
            "Invalid model provider. Use `openai` or `ollama`."
        ) from exc


def normalize_ollama_base_url(url: str | None) -> str:
    cleaned = (url or "http://localhost:11434/v1/").strip().rstrip("/")
    if cleaned.endswith("/v1"):
        return f"{cleaned}/"
    return f"{cleaned}/v1/"


def resolve_generation_model(
    provider: ModelProviderKind, explicit_model: str | None = None
) -> str:
    load_dotenv()
    if explicit_model:
        return explicit_model.strip()

    generic = os.environ.get("SKILL_GENERATOR_MODEL", "").strip()
    if generic:
        return generic

    if provider is ModelProviderKind.OLLAMA:
        ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
        if not ollama_model:
            raise RuntimeError(
                "OLLAMA_MODEL is required when provider is `ollama`. "
                "Add it to .env or pass --model."
            )
        return ollama_model

    return "gpt-5.3-codex"


def resolve_ollama_config(base_url: str | None = None) -> tuple[str, str]:
    load_dotenv()
    resolved_base_url = normalize_ollama_base_url(base_url or os.environ.get("OLLAMA_BASE_URL"))
    api_key = os.environ.get("OLLAMA_API_KEY", "").strip() or "ollama"
    return resolved_base_url, api_key
