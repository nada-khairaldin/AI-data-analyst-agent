import os

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import (
    build_agent_prompt,
    build_retry_prompt
)

from .schemas import (
    STATUSES,
    TOOL_SCHEMAS
)

from .validators import (
    validate_agent_output
)


load_dotenv()

API_KEY = os.getenv("HUGGINGFACE_API_KEY")


def build_agent_input(state):
    return {
        "question": state["question"],
        "schema": state["schema"],
        "unavailable_columns": (
            state["unavailable_columns"]
        ),
        "tool_schemas": TOOL_SCHEMAS
    }


def call_llm(prompt):
    if not API_KEY:
        raise RuntimeError(
            "HUGGINGFACE_API_KEY is not configured."
        )

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=API_KEY,
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

    return completion.choices[0].message.content


def run_agent(
    state,
    max_attempts=2
):
    agent_input = build_agent_input(state)

    prompt = build_agent_prompt(
        agent_input
    )

    validation_error = None

    for attempt in range(max_attempts):
        try:
            raw_output = call_llm(prompt)

        except Exception as error:
            state["status"] = STATUSES["FAILED"]
            state["error"] = str(error)

            return state

        (
            is_valid,
            agent_output,
            validation_error
        ) = validate_agent_output(
            raw_output,
            state["schema"]
        )

        if is_valid:
            state["status"] = agent_output["status"]

            state["analysis_plan"] = (
                agent_output["analysis_plan"]
            )

            state["chart_plan"] = (
                agent_output.get("chart_plan")
            )

            state["message"] = (
                agent_output.get("message")
            )

            return state

        prompt = build_retry_prompt(
            agent_input=agent_input,
            validation_error=validation_error,
            previous_output=raw_output
        )

    state["status"] = STATUSES["FAILED"]
    state["error"] = validation_error

    return state