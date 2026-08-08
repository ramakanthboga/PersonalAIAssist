"""Build example questions from the user's uploaded document names."""

from __future__ import annotations

import re


def _short_name(filename: str, max_len: int = 56) -> str:
    name = re.sub(r"\.[^.]+$", "", filename).replace("_", " ").replace("-", " ").strip()
    name = re.sub(r"\s+", " ", name)
    if len(name) <= max_len:
        return name
    return name[: max_len - 1].rstrip() + "…"


def _learning_goal(user_query: str | None) -> str | None:
    """Extract a short learning/topic goal from a suggest-prompts query, if any."""
    if not user_query:
        return None
    q = user_query.strip()
    patterns = [
        r"suggest(?:\s+\w+){0,4}\s+prompts?\s+(?:for|about|on|to)\s+(.+)$",
        r"prompts?\s+(?:for|about|on|to)\s+(.+)$",
        r"(?:help\s+me\s+)?learn(?:ing)?\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if m:
            goal = re.sub(r"[?.!]+$", "", m.group(1)).strip()
            # "for learning X" → prefer topic X
            goal = re.sub(r"^(?:learning|to\s+learn|studying)\s+", "", goal, flags=re.IGNORECASE)
            if goal and len(goal) > 2:
                return goal[:80]
    return None


def example_prompts_for_documents(
    filenames: list[str],
    *,
    limit: int = 6,
    user_query: str | None = None,
) -> list[str]:
    """Return example questions tailored to uploaded files (and optional goal)."""
    goal = _learning_goal(user_query)

    if not filenames:
        if goal:
            return [
                f"What does my document say about {goal}?",
                f"Explain {goal} with examples from the document",
                f"List the key points related to {goal}",
            ]
        return [
            "Summarize my uploaded documents",
            "What are the main topics covered?",
            "List the key points from my documents",
        ]

    # Prefer the scoped / first document for focused learning prompts
    primary = _short_name(filenames[0], 64)
    prompts: list[str] = []

    if goal:
        prompts.extend(
            [
                f"Explain {goal} using only this document, with examples",
                f"List the top risks or controls related to {goal}",
                f"What does the document recommend for {goal}?",
                f"Give a beginner learning path for {goal} based on the document sections",
                f"Summarize the sections most relevant to {goal}",
            ]
        )
    else:
        prompts.extend(
            [
                f"Summarize {primary}",
                f"What are the top risks or key points in {primary}?",
                f"Explain the first major section of {primary} with examples from the document",
            ]
        )

    for name in filenames[1:3]:
        short = _short_name(name)
        prompts.append(f"Summarize {short}")

    seen: set[str] = set()
    unique: list[str] = []
    for p in prompts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
        if len(unique) >= limit:
            break
    return unique


def format_suggested_prompts_markdown(
    filenames: list[str],
    *,
    user_query: str | None = None,
) -> str:
    """Markdown reply for 'suggest prompts' when LLM grounding is unavailable."""
    examples = example_prompts_for_documents(filenames, user_query=user_query)
    goal = _learning_goal(user_query)

    if filenames:
        if len(filenames) == 1:
            intro = (
                f"Here are prompts you can ask about **{_short_name(filenames[0], 72)}**"
                + (f" (focused on **{goal}**)" if goal else "")
                + ":\n"
            )
        else:
            intro = (
                "Here are prompts grounded in your selected documents"
                + (f" for **{goal}**" if goal else "")
                + ":\n"
            )
    else:
        intro = "Try questions like these once you upload documents:\n"

    lines = [intro]
    for i, prompt in enumerate(examples, 1):
        lines.append(f"{i}. {prompt}")

    lines.append(
        "\nTip: ask for summaries, lists, definitions, or "
        "“explain X with examples from the document.”"
    )
    return "\n".join(lines)
