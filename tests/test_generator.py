from skillforge.generator import SkillForge


def test_model_settings_omit_temperature_for_codex_models() -> None:
    forge = SkillForge(model="gpt-5.3-codex", reasoning_effort="medium")

    settings = forge._model_settings()

    assert settings.temperature is None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "medium"
