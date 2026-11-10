import json

import pandas as pd

from .llm import complete
from .validators import validate_explainer_output


def serialize_result(result):
    if isinstance(result, pd.DataFrame):
        return result.to_dict(orient="records")

    return result


def build_explainer_prompt(
    question,
    analysis_plan,
    result
):
    serialized_result = serialize_result(result)

    return f"""
You are a data analysis result explainer.

User question:
{question}

Analysis plan:
{json.dumps(analysis_plan, indent=2)}

Verified analysis result:
{json.dumps(
    serialized_result,
    indent=2,
    default=str
)}

Return ONLY valid JSON in exactly this structure:

{{
    "summary": "short natural-language answer"
}}

Rules:
- Use only the provided verified result.
- Do not recalculate values.
- Do not invent or modify numbers.
- Answer the user's original question directly.
- Mention the most important finding when useful.
- Mention relevant filters or grouping only when useful.
- Keep the summary to 1-3 short sentences.
- Do NOT reproduce the dataset.
- Do NOT reproduce the full result.
- Do NOT create a table.
- Do NOT use Markdown tables.
- Do NOT list every row or category.
- Do NOT use bullet points.
- The full structured result is displayed separately in the UI.
- Do not mention Pandas, tools, prompts, or implementation details.
"""

def call_explainer_llm(prompt):
    """Client construction moved to app/agent/llm.py; logic unchanged.

    Note for feature 5.5: this still asks for and validates JSON. Streaming
    the answer requires plain text, because a half-written JSON object cannot
    be shown to anyone — see docs/PLAN.md §6B. That change belongs with the
    streaming work, not with this move.
    """
    raw_output = complete(prompt)

    is_valid, summary, error = validate_explainer_output(
    raw_output
    )

    if not is_valid:
        raise ValueError(error)

    return summary



def explain_result(
    question,
    analysis_plan,
    result
):
    prompt = build_explainer_prompt(
        question=question,
        analysis_plan=analysis_plan,
        result=result
    )

    return call_explainer_llm(prompt)