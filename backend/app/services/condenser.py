"""Rewrite a follow-up into one standalone question (PLAN §6.4).

This is the ONLY place conversation history is used. The planner and the
explainer never see it, so `prompts.py` and `validators.py` stay untouched and
nothing that works today can regress.

The output is a small JSON object with a `kind`, so an instruction like "only
2024 from now on" costs 1 call instead of 3. Every parse or shape failure
falls back to treating the raw message as the question — a pass-through is
exactly what a first message does, so the condenser can never become a new way
for the whole chat to fail.
"""

import json
import logging
import pathlib
import re

from app.agent.llm import FAST, LLMError, complete
from app.agent.text_utils import strip_code_fence
from app.config import settings

logger = logging.getLogger(__name__)

PROMPT_PATH = pathlib.Path(__file__).resolve().parent.parent / "prompts" / "condenser.txt"

QUESTION = "question"
INSTRUCTION = "instruction"
CLARIFICATION_ANSWER = "clarification_answer"
KINDS = (QUESTION, INSTRUCTION, CLARIFICATION_ANSWER)

# A condensed question longer than this is a sign the model explained itself
# rather than answering. Falling back is safer than planning from prose.
MAX_QUESTION_CHARS = 300

_LABEL = re.compile(r"^\s*(question|answer)\s*:\s*", re.I)


def _template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_prompt(*, question, schema, excluded_columns, fact_sheet, window) -> str:
    excluded = (
        "\n".join(f"- {name}: {reason}" for name, reason in (excluded_columns or {}).items())
        or "none"
    )
    columns = "\n".join(f"- {name}: {dtype}" for name, dtype in (schema or {}).items())
    return (
        _template()
        .replace("{schema}", columns or "none")
        .replace("{excluded_columns}", excluded)
        .replace("{fact_sheet}", (fact_sheet or "").strip() or "none")
        .replace("{window}", window or "none")
        .replace("{question}", question)
    )


def passthrough(question, reason=None):
    """The safe answer: the raw message, treated as a question."""
    if reason:
        logger.info("Condenser fell back to the raw message: %s", reason)
    return {"kind": QUESTION, "question": question, "fell_back": True}


def parse(raw, question):
    """Parse the model's reply. Any doubt at all becomes a pass-through."""
    text = strip_code_fence(raw or "")
    if not text.strip():
        return passthrough(question, "empty reply")

    try:
        payload = json.loads(text)
    except ValueError:
        # Plain text is what the pre-JSON design returned, and a bare question
        # is still usable — so accept one clean line rather than discarding it.
        line = _LABEL.sub("", text.strip().strip('"').strip("'")).strip()
        # But text that OPENS like JSON is truncated JSON, not a question.
        # Planning from '{"kind": "question", "question' would be worse than
        # falling back.
        if line.startswith(("{", "[")):
            return passthrough(question, "reply looked like truncated JSON")
        if line and "\n" not in line and len(line) <= MAX_QUESTION_CHARS:
            return {"kind": QUESTION, "question": line, "fell_back": False}
        return passthrough(question, "reply was neither JSON nor a single line")

    if not isinstance(payload, dict):
        return passthrough(question, "reply was not a JSON object")

    kind = str(payload.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return passthrough(question, f"unknown kind {kind!r}")

    if kind == INSTRUCTION:
        acknowledgement = str(payload.get("acknowledgement") or "").strip()
        if not acknowledgement:
            return passthrough(question, "instruction with no acknowledgement")
        return {
            "kind": INSTRUCTION,
            "acknowledgement": acknowledgement[:500],
            "fell_back": False,
        }

    condensed = _LABEL.sub("", str(payload.get("question") or "").strip()).strip()
    condensed = condensed.strip('"').strip("'").strip()
    if not condensed or "\n" in condensed or len(condensed) > MAX_QUESTION_CHARS:
        return passthrough(question, "question was empty, multi-line or too long")

    return {"kind": kind, "question": condensed, "fell_back": False}


def condense(*, question, schema, excluded_columns, fact_sheet, window):
    """Returns {kind, question|acknowledgement, fell_back}.

    Never raises for a model problem: the caller gets a usable question either
    way. A rate limit still propagates, because that is an infrastructure
    failure the user needs told about.
    """
    if not settings.condenser_enabled:
        return passthrough(question, "CONDENSER_ENABLED is false")

    prompt = build_prompt(
        question=question,
        schema=schema,
        excluded_columns=excluded_columns,
        fact_sheet=fact_sheet,
        window=window,
    )

    try:
        raw = complete(prompt, role=FAST)
    except LLMError:
        raise
    except Exception as error:
        return passthrough(question, f"{type(error).__name__}: {error}")

    return parse(raw, question)
