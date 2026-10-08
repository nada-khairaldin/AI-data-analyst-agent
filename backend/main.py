from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from validation import validate_question
from data_utils import get_schema
from agent import create_agent_state, run_agent, STATUSES
from agent.explainer import explain_result
from tools import execute_plan
app = FastAPI(title="Data Analysis Agent API")

# Add CORS middleware to allow the React frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Default Vite dev server ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    session_id: str
    query: str
    
@app.get("/")
def read_root():
    return {"message": "Welcome to the Data Analysis Agent API!"}

@app.post("/api/analyze")
def analyze_query(request: QueryRequest):
    if request.session_id not in sessions:
        return {"status": "error", "message": "Session not found. Please upload a file first."}
        
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
        unavailable_columns={} # Columns were dropped during upload
    )
    
    state = run_agent(state)
    
    if state["status"] == STATUSES["FAILED"]:
        return {"status": "error", "message": f"Agent failed: {state['error']}"}
    elif state["status"] == STATUSES["NEEDS_CLARIFICATION"]:
        return {"status": "clarification", "message": state["message"]}
    elif state["status"] == STATUSES["CANNOT_ANSWER"]:
        return {"status": "warning", "message": state["message"]}
    elif state["status"] == STATUSES["READY"]:
        try:
            result = execute_plan(working_df, state["analysis_plan"])
        except Exception as error:
            return {"status": "error", "message": f"Analysis failed: {str(error)}"}
            
        state["result"] = result
        
        try:
            state["answer"] = explain_result(question, state["analysis_plan"], result)
        except Exception as error:
            return {"status": "error", "message": f"Failed to explain the result: {str(error)}"}
            
        # Format the result for JSON
        import math
        formatted_result = (
            result.fillna("").to_dict(orient="records") if isinstance(result, pd.DataFrame) else result
        )
        
        # Save to history
        history_item = {
            "question": question,
            "analysis_plan": state["analysis_plan"],
            "chart_plan": state["chart_plan"],
            "result": formatted_result,
            "answer": state["answer"]
        }
        session_data["history"].append(history_item)
        
        return {
            "status": "success",
            "answer": state["answer"],
            "analysis_plan": state["analysis_plan"],
            "chart_plan": state["chart_plan"],
            "result_data": formatted_result
        }

import io
import uuid
from typing import Dict, Any
from validation import load_csv, prepare_dataframe

# In-memory storage for uploaded dataframes (Session Management)
# In a real app, you'd use a database and cloud storage (S3).
sessions: Dict[str, Any] = {}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # Read file contents into memory
    contents = await file.read()
    file_obj = io.BytesIO(contents)
    
    # 1. Load and validate CSV structure
    df, error_message = load_csv(file_obj)
    if error_message:
        return {"status": "error", "message": error_message}
        
    # 2. Prepare and clean the dataframe
    result = prepare_dataframe(df)
    
    if result["errors"]:
        return {"status": "error", "message": "Data validation failed", "details": result["errors"]}
        
    # 3. Create a unique session ID for this user's dataset
    session_id = str(uuid.uuid4())
    
    # Remove unavailable columns before saving
    working_df = result["working_df"]
    working_df = working_df.drop(columns=list(result["unavailable_columns"].keys()))
    
    # Save to session
    sessions[session_id] = {
        "df": working_df,
        "history": [] # To store chat history later
    }
    
    return {
        "status": "success",
        "session_id": session_id,
        "warnings": result["warnings"],
        "conversions": result["conversions"],
        "unavailable_columns": result["unavailable_columns"],
        "row_count": len(working_df),
        "column_count": len(working_df.columns),
        "schema": get_schema(working_df)
    }
