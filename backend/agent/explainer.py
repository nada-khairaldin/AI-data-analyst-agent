import json
import os

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from agent.validators import validate_explainer_output


load_dotenv()

API_KEY = os.getenv("HUGGINGFACE_API_KEY")


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
    if not API_KEY:
        raise RuntimeError(
            "HUGGINGFACE_API_KEY is not configured."
        )

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=API_KEY
    )

    completion = client.chat.completions.create(
        model="Qwen/Qwen3.8-Flash-Next:featherless-ai",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_output = completion.choices[0].message.content

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