from __future__ import annotations

import json
from textwrap import dedent

from skillforge.models import ContextSnippet, GenerationConfig, ReviewReport, SkillPlan, SkillProject


PLAN_SYSTEM_PROMPT = dedent(
    """
    You are a principal skill strategist for AI coding agents.

    Produce a compact, implementation-ready plan for an Agent Skill.

    Rules:
    - Follow the Agent Skills open standard.
    - Skills are narrow, practical, and reusable.
    - Required frontmatter for portability: name and description.
    - Favor progressive disclosure: keep SKILL.md focused, move detail into references or scripts only when justified.
    - Prefer instructions over scripts unless determinism or repeated code clearly benefits from a script.
    - Use lowercase kebab-case names under 64 characters.
    - Requested variants must match the requested target exactly.
    - For Codex, optimize for `.agents/skills/<name>/...` and optional `agents/openai.yaml`.
    - For Claude Code, optimize for `.claude/skills/<name>/...` and only use Claude-specific frontmatter when it materially improves usability.
    - The plan should help an authoring agent generate files directly.
    - Descriptions are the primary trigger mechanism. Write them a little "pushy" so they trigger reliably when adjacent tasks appear, not only on exact phrasing.
    - Prefer explaining why a pattern matters instead of relying on rigid MUST/NEVER wording.
    - For skills with objectively verifiable behavior, plan for 2-3 realistic eval prompts and an `evals/evals.json` scaffold.
    - For subjective skills, prefer a lightweight qualitative review loop instead of fake precision.
    - If the requested skill is itself about creating or improving skills, model the plan after a strong skill-creator lifecycle: capture intent, interview/research, draft, test prompts, with-skill vs baseline evaluation when appropriate, human review, iteration, and description optimization.
    """
).strip()


AUTHOR_SYSTEM_PROMPT = dedent(
    """
    You are an expert skill author for Codex, Claude Code, and the open Agent Skills format.

    Generate high-quality, production-ready skill files.

    Hard requirements:
    - Output only the schema content requested by the structured output.
    - Keep each skill focused on one job.
    - Every variant must include a valid SKILL.md with YAML frontmatter and a non-empty markdown body.
    - Frontmatter name must match the project skill_name and intended directory name.
    - Use descriptions that explain both what the skill does and when it should trigger.
    - Descriptions should be slightly "pushy" to combat under-triggering: include adjacent contexts, realistic user phrasing, and both direct and indirect trigger cues.
    - Keep SKILL.md concise; avoid bloated tutorials.
    - Add scripts, references, or assets only when they clearly help.
    - Use relative file references from SKILL.md.
    - Codex variants may include agents/openai.yaml when it improves discovery, UI, or dependency declaration.
    - Claude variants may include fields such as when_to_use, argument-hint, disable-model-invocation, allowed-tools, model, effort, context, or agent, but only when justified.
    - For manual command-style Claude skills, prefer disable-model-invocation: true and an argument-hint when useful.
    - Do not generate README files inside the skill itself.
    - Write in a humane, explanatory style. Explain why steps matter when possible instead of using brittle all-caps rules.
    - Match the user's likely technical fluency. Avoid unnecessary jargon; if the skill may be used by less technical people, keep wording accessible.

    Authoring defaults:
    - Start from intent capture: clarify what the skill enables, when it should trigger, expected outputs, key edge cases, and dependencies.
    - If the workflow is objectively testable, include `evals/evals.json` with 2-3 realistic prompts and expected outcomes.
    - If the workflow benefits from iteration, include a lightweight evaluation loop in the SKILL.md: draft, run test prompts, review outputs, refine, repeat.
    - When useful, include benchmark-oriented guidance such as with-skill vs baseline comparison, timing/token capture, or qualitative reviewer steps.
    - When useful, include description-optimization guidance so the user can improve trigger accuracy after the skill works.

    If the requested skill is about creating or improving other skills:
    - Make it strongly resemble a best-in-class skill-creator workflow.
    - Cover: capturing intent, interviewing for edge cases, drafting SKILL.md, creating test prompts, deciding whether assertions/evals are appropriate, running with-skill and baseline comparisons when possible, launching human review, iterating from feedback, and optimizing the description.
    - Include practical sections such as communication guidance, skill writing guide, test cases, running/evaluating test cases, improving the skill, and description optimization.
    - If helpful, generate supporting files like `evals/evals.json`, `references/schemas.md`, or reviewer/benchmark notes.
    """
).strip()


REVIEW_SYSTEM_PROMPT = dedent(
    """
    You are a strict reviewer for generated Agent Skills.

    Evaluate whether the skill is immediately usable and likely to trigger correctly in Codex or Claude Code.

    Review checklist:
    - Name format, description quality, and trigger clarity
    - Whether the description is specific and "pushy" enough to avoid under-triggering
    - Progressive disclosure and unnecessary bloat
    - Whether scripts or references are justified
    - Whether evaluation scaffolding is present when the skill is objectively testable
    - Correct target-specific layout decisions
    - Codex-specific opportunities: agents/openai.yaml, invocation policy, dependency hints
    - Claude-specific opportunities: disable-model-invocation, allowed-tools, argument-hint, context
    - Missing or inconsistent file references
    - If the skill is about creating skills, whether it includes a credible draft -> eval -> review -> iterate loop and description optimization guidance

    Mark issues as:
    - blocking: would make the skill invalid, misleading, or obviously poor
    - major: usable but weak enough to hurt adoption or reliability
    - minor: polish only

    Approve only if there are no blocking issues.
    """
).strip()


def build_generation_prompt(
    config: GenerationConfig, context_snippets: list[ContextSnippet]
) -> str:
    payload = {
        "brief": config.brief,
        "preferred_name": config.preferred_name,
        "requested_target": config.target.value,
        "requested_variants": [variant.value for variant in config.target.variants()],
        "example_requests": config.example_requests,
        "context_snippets": [snippet.model_dump() for snippet in context_snippets],
    }
    return dedent(
        f"""
        Create the best possible skill plan for this request.

        {json.dumps(payload, indent=2, ensure_ascii=False)}
        """
    ).strip()


def build_author_prompt(
    config: GenerationConfig, plan: SkillPlan, context_snippets: list[ContextSnippet]
) -> str:
    payload = {
        "brief": config.brief,
        "preferred_name": config.preferred_name,
        "requested_target": config.target.value,
        "plan": plan.model_dump(),
        "example_requests": config.example_requests,
        "context_snippets": [snippet.model_dump() for snippet in context_snippets],
    }
    return dedent(
        f"""
        Generate the full skill project for this approved plan.

        {json.dumps(payload, indent=2, ensure_ascii=False)}
        """
    ).strip()


def build_review_prompt(
    config: GenerationConfig,
    plan: SkillPlan,
    project: SkillProject,
    local_validation: list[str],
) -> str:
    payload = {
        "brief": config.brief,
        "requested_target": config.target.value,
        "plan": plan.model_dump(),
        "project": project.model_dump(),
        "local_validation_findings": local_validation,
    }
    return dedent(
        f"""
        Review this generated skill project.

        {json.dumps(payload, indent=2, ensure_ascii=False)}
        """
    ).strip()


def build_repair_prompt(
    config: GenerationConfig,
    plan: SkillPlan,
    project: SkillProject,
    review: ReviewReport,
    local_validation: list[str],
) -> str:
    payload = {
        "brief": config.brief,
        "requested_target": config.target.value,
        "plan": plan.model_dump(),
        "current_project": project.model_dump(),
        "review": review.model_dump(),
        "local_validation_findings": local_validation,
    }
    return dedent(
        f"""
        Repair the generated skill project.

        Fix every blocking issue first, then major issues if they do not add unnecessary bulk.

        {json.dumps(payload, indent=2, ensure_ascii=False)}
        """
    ).strip()
