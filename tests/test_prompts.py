from skillforge.prompts import AUTHOR_SYSTEM_PROMPT, PLAN_SYSTEM_PROMPT, REVIEW_SYSTEM_PROMPT


def test_plan_prompt_includes_skill_creator_lifecycle() -> None:
    lowered = PLAN_SYSTEM_PROMPT.lower()
    assert "capture intent" in lowered
    assert "description optimization" in lowered
    assert "baseline" in lowered


def test_author_prompt_includes_eval_and_iteration_guidance() -> None:
    lowered = AUTHOR_SYSTEM_PROMPT.lower()
    assert "evals/evals.json" in lowered
    assert "with-skill and baseline" in lowered
    assert "description optimization" in lowered
    assert "communication guidance" in lowered


def test_review_prompt_checks_undertriggering_and_eval_scaffolding() -> None:
    lowered = REVIEW_SYSTEM_PROMPT.lower()
    assert "under-triggering" in lowered
    assert "evaluation scaffolding" in lowered
    assert "iterate loop" in lowered
