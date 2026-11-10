"""The original /api/upload and /api/analyze endpoints, moved verbatim.

This file was ``backend/main.py``. It is kept working, unchanged in behaviour,
so that step A3 is a pure restructure with nothing to regress. Phase B
replaces both endpoints with the real contract in docs/API_CONTRACT.md, at
which point this module is deleted.

Known limitations, all inherited and all deliberately left alone here:

- ``sessions`` is a module-level dict, so every dataset is lost on restart and
  a second worker process cannot see the first one's uploads. This is the main
  thing phase A6/A7 exists to fix.
- Errors are returned as HTTP 200 with ``{"status": "error"}``. The contract
  moves these to real status codes; changing it now would break nothing but
  would also mislead anyone reading this as current.
- ``unavailable_columns`` is passed to the agent as ``{}`` because the columns
  have already been dropped, so the agent can only say "unknown column", never
  "excluded for quality reasons". Fixed in feature 4, which has the
  dataset_columns table to read from.

Three things *were* changed, none of them behavioural:
- imports moved to the top of the file (they were half way down, after the
  endpoint that used them) and repointed at the app package;
- an unused ``import math`` removed;
- a final ``else`` added to the status chain in analyze_query, which could
  previously fall through and return ``None`` -> JSON ``null``.
"""

import io
import uuid
from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.agent import STATUSES, create_agent_state, run_agent
from app.agent.llm import LLMError
from app.agent.explainer import explain_result
from app.agent.tools import execute_plan
from app.data.data_utils import get_schema
from app.data.validation import load_csv, prepare_dataframe, validate_question

router = APIRouter(tags=["legacy"])

# In-memory storage for uploaded dataframes. See the module docstring.
sessions: Dict[str, Any] = {}


class QueryRequest(BaseModel):
    session_id: str
    query: str


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    file_obj = io.BytesIO(contents)

    # 1. Load and validate CSV structure
    df, error_message = load_csv(file_obj)
    if error_message:
        return {"status": "error", "message": error_message}

    # 2. Prepare and clean the dataframe
    result = prepare_dataframe(df)

    if result["errors"]:
        return {
            "status": "error",
            "message": "Data validation failed",
            "details": result["errors"],
        }

    # 3. Create a unique session ID for this user's dataset
    session_id = str(uuid.uuid4())

    # Remove unavailable columns before saving
    working_df = result["working_df"]
    working_df = working_df.drop(columns=list(result["unavailable_columns"].keys()))

    sessions[session_id] = {
        "df": working_df,
        "history": [],  # collected but never read; see the module docstring
    }

    return {
        "status": "success",
        "session_id": session_id,
        "warnings": result["warnings"],
        "conversions": result["conversions"],
        "unavailable_columns": result["unavailable_columns"],
        "row_count": len(working_df),
        "column_count": len(working_df.columns),
        "schema": get_schema(working_df),
    }


@router.post("/api/analyze")
def analyze_query(request: QueryRequest):
    if request.session_id not in sessions:
        return {
            "status": "error",
            "message": "Session not found. Please upload a file first.",
        }

    session_data = sessions[request.session_id]
    working_df = session_data["df"]
    question = request.query

    is_valid, error_message = validate_question(question)
    if not is_valid:
        return {"status": "error", "message": error_message}

    schema = get_schema(working_df)

    state = create_agent_state(
        question=question,
        schema=schema,
        unavailable_columns={},  # columns were dropped during upload
    )

    state = run_agent(state)

    if state["status"] == STATUSES["FAILED"]:
        return {"status": "error", "message": f"Agent failed: {state['error']}"}

    if state["status"] == STATUSES["NEEDS_CLARIFICATION"]:
        return {"status": "clarification", "message": state["message"]}

    if state["status"] == STATUSES["CANNOT_ANSWER"]:
        return {"status": "warning", "message": state["message"]}

    if state["status"] == STATUSES["READY"]:
        try:
            result = execute_plan(working_df, state["analysis_plan"])
        except Exception as error:
            return {"status": "error", "message": f"Analysis failed: {str(error)}"}

        state["result"] = result

        try:
            state["answer"] = explain_result(
                question, state["analysis_plan"], result
            )
        except LLMError:
            # Mapped to a real status code by app/api/errors.py. Swallowing it
            # here would turn a 429 into an HTTP 200 the frontend reads as a
            # normal failure.
            raise
        except Exception as error:
            return {
                "status": "error",
                "message": f"Failed to explain the result: {str(error)}",
            }

        formatted_result = (
            result.fillna("").to_dict(orient="records")
            if isinstance(result, pd.DataFrame)
            else result
        )

        session_data["history"].append(
            {
                "question": question,
                "analysis_plan": state["analysis_plan"],
                "chart_plan": state["chart_plan"],
                "result": formatted_result,
                "answer": state["answer"],
            }
        )

        return {
            "status": "success",
            "answer": state["answer"],
            "analysis_plan": state["analysis_plan"],
            "chart_plan": state["chart_plan"],
            "result_data": formatted_result,
        }

    # Previously absent. A PENDING or COMPLETED status fell off the end of the
    # chain and the function returned None, which FastAPI serialises as null:
    # a response the frontend cannot tell from a successful empty answer.
    return {
        "status": "error",
        "message": f"The agent finished in an unexpected state: {state['status']}",
    }
