from .llm import PLANNER, LLMError, complete

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
    """Kept as a named function so run_agent below is untouched.

    Uses the PLANNER model: this call has to produce a tool plan that survives
    validators.py, which is the one job worth the stronger model. Everything
    about the client — model, key, timeout, 429 backoff — lives in
    app/agent/llm.py.
    """
    return complete(prompt, role=PLANNER)


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

        except LLMError:
            # Deliberately NOT swallowed into status=FAILED. A rate limit or
            # an unreachable provider is an infrastructure failure with its
            # own HTTP status and its own user action ("wait and retry"),
            # whereas FAILED means "the model answered and the answer was
            # unusable". Collapsing the two would report a 429 as a 200 with
            # an agent error, which the frontend cannot act on.
            raise

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