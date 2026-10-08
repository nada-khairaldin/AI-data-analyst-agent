from .schemas import STATUSES


def create_agent_state(
    question,
    schema,
    unavailable_columns
):
    return {
        "question": question,
        "schema": schema,
        "unavailable_columns": unavailable_columns,

        "status": STATUSES["PENDING"],

        "analysis_plan": [],
        "chart_plan": None,
        "message": None,
        "result": None,
        "answer": None,
        "error": None
    }