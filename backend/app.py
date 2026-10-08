import streamlit as st
import pandas as pd
from agent.explainer import explain_result
from charting import render_chart



from agent import (
    create_agent_state,
    run_agent,
    STATUSES,
)
from data_utils import get_schema
from tools import execute_plan
from validation import load_csv, prepare_dataframe, validate_question


if "history" not in st.session_state:
    st.session_state.history = []

if "selected_history" not in st.session_state:
    st.session_state.selected_history = None


st.title("AI Data Analyst")

uploaded_file = st.file_uploader(
    "Upload your CSV file",
    type=["csv"]
)

# No file uploaded yet
if uploaded_file is None:
    st.info("Please upload a CSV file to continue.")
    st.stop()


# ==========================================
# Load CSV
# ==========================================

df, error_message = load_csv(uploaded_file)

if error_message:
    st.error(error_message)
    st.stop()


# ==========================================
# Validate + Normalize
# ==========================================

result = prepare_dataframe(df)

if result["errors"]:
    for error in result["errors"]:
        st.error(error)

    st.stop()


for warning in result["warnings"]:
    st.warning(warning)


unavailable_columns = result["unavailable_columns"]

if unavailable_columns:
    with st.expander("Unavailable columns for analysis"):
        for column, reason in unavailable_columns.items():
            st.write(f"- {column}: {reason}")


conversions = result["conversions"]

if conversions:
    with st.expander("Data type conversions"):
        for column, info in conversions.items():
            st.write(
                f"- {column}: "
                f"{info['original_type']} → {info['converted_to']} "
                f"({info['success_rate']:.1%} success)"
            )


# Use normalized data for analysis
working_df = result["working_df"]

working_df = working_df.drop(
    columns=list(unavailable_columns.keys())
)


# ==========================================
# Dataset Ready
# ==========================================

st.success(
    "CSV file loaded successfully and is ready for analysis!"
)

st.subheader("Dataset Summary")

col1, col2 = st.columns(2)

with col1:
    st.metric("Rows", working_df.shape[0])

with col2:
    st.metric("Columns", working_df.shape[1])


schema_df = pd.DataFrame({
    "Column": working_df.columns,
    "Data Type": working_df.dtypes.astype(str).values
})

st.subheader("Schema")
st.dataframe(schema_df)


st.subheader("Dataset Preview")
st.dataframe(working_df.head())


# ==========================================
# Ask Question
# ==========================================

st.subheader("Ask a Question")

question = st.text_input(
    "Ask a question about your data"
)

analyze_button = st.button("Analyze")

if analyze_button:

    is_valid, error_message = validate_question(question)

    if not is_valid:
        st.error(error_message)
        st.stop()

    schema = get_schema(working_df)

    state = create_agent_state(
        question=question,
        schema=schema,
        unavailable_columns=unavailable_columns
    )

    status_box = st.empty()

    status_box.info("Understanding your question...")

    state = run_agent(state)

    # =========================================================
    # Agent status handling
    # =========================================================

    if state["status"] == STATUSES["FAILED"]:

        status_box.empty()

        st.error(
            f"Agent failed: {state['error']}"
        )

        st.stop()

    elif state["status"] == STATUSES["NEEDS_CLARIFICATION"]:

        status_box.empty()

        st.info(
            state["message"]
        )

        st.stop()

    elif state["status"] == STATUSES["CANNOT_ANSWER"]:

        status_box.empty()

        st.warning(
            state["message"]
        )

        st.stop()

    elif state["status"] == STATUSES["READY"]:

        # =====================================================
        # Execute analysis
        # =====================================================

        status_box.info(
            "Executing analysis..."
        )

        try:

            result = execute_plan(
                working_df,
                state["analysis_plan"]
            )

        except Exception as error:

            status_box.empty()

            st.error(
                f"Analysis failed: {error}"
            )

            st.stop()

        state["result"] = result

        # =====================================================
        # Generate explanation
        # =====================================================

        status_box.info(
            "Preparing explanation..."
        )

        try:

            state["answer"] = explain_result(
                question,
                state["analysis_plan"],
                result
            )

        except Exception as error:

            status_box.empty()

            st.error(
                f"Failed to explain the result: {error}"
            )

            st.stop()

        state["status"] = STATUSES["COMPLETED"]

        # =====================================================
        # Save history
        # =====================================================

        history_item = {
            "question": question,

            "analysis_plan": state["analysis_plan"],

            "chart_plan": state["chart_plan"],

            "result": (
                result.to_dict(orient="records")
                if isinstance(result, pd.DataFrame)
                else result
            ),

            "answer": state["answer"]
        }

        st.session_state.history.append(
            history_item
        )

        # =====================================================
        # Display result
        # =====================================================

        status_box.empty()

        st.subheader(
            "Analysis Result"
        )

        # -----------------------------------------------------
        # 1. Final answer - ALWAYS VISIBLE
        # -----------------------------------------------------

        st.write(
            state["answer"]
        )

        # -----------------------------------------------------
        # 2. Result / Chart - ALWAYS VISIBLE
        # -----------------------------------------------------

        if isinstance(result, pd.DataFrame):

            st.dataframe(
                result,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.metric(
                label="Result",
                value=result
            )

        # Chart stays outside the expander
        render_chart(
            result,
            state["chart_plan"]
        )

        # -----------------------------------------------------
        # 3. Analysis details - HIDDEN
        # -----------------------------------------------------

        with st.expander(
            "View analysis details"
        ):

            st.markdown(
                "### Analysis Plan"
            )

            st.json(
                state["analysis_plan"]
            )


# =============================================================
# Sidebar - Previous Questions
# =============================================================

with st.sidebar:

    st.subheader(
        "Previous Questions"
    )

    if not st.session_state.history:

        st.caption(
            "No previous questions yet."
        )

    else:

        for index, item in enumerate(
            reversed(st.session_state.history)
        ):

            if st.button(
                item["question"],
                key=f"history_{index}"
            ):

                st.session_state.selected_history = item


# =============================================================
# Previous Analysis
# =============================================================

selected_history = st.session_state.selected_history

if selected_history is not None:

    st.subheader(
        "Previous Analysis"
    )

    # ---------------------------------------------------------
    # 1. Final answer - ALWAYS VISIBLE
    # ---------------------------------------------------------

    st.write(
        selected_history["answer"]
    )

    # ---------------------------------------------------------
    # 2. Result - ALWAYS VISIBLE
    # ---------------------------------------------------------

    result = selected_history["result"]

    if isinstance(result, list):

        result_df = pd.DataFrame(
            result
        )

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )

        # Chart stays outside the expander
        render_chart(
            result_df,
            selected_history["chart_plan"]
        )

    else:

        st.metric(
            label="Result",
            value=result
        )

    # ---------------------------------------------------------
    # 3. Analysis Plan - HIDDEN
    # ---------------------------------------------------------

    with st.expander(
        "View analysis details"
    ):

        st.markdown(
            "### Analysis Plan"
        )

        st.json(
            selected_history["analysis_plan"]
        )