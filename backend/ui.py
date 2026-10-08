import streamlit as st
import pandas as pd


# ============================================================
# Custom Styling
# ============================================================

def load_custom_css():
    st.markdown(
        """
        <style>

        /* =========================
           Global
        ========================= */

        .block-container {
            max-width: 1200px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        /* =========================
           Header
        ========================= */

        .app-title {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            margin-bottom: 0.25rem;
        }

        .app-subtitle {
            color: #6b7280;
            font-size: 1rem;
            margin-bottom: 2rem;
        }

        /* =========================
           Section Labels
        ========================= */

        .section-label {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #6b7280;
            margin-bottom: 0.6rem;
        }

        /* =========================
           Sidebar
        ========================= */

        section[data-testid="stSidebar"] {
            border-right: 1px solid #e5e7eb;
        }

        .sidebar-dataset {
            padding: 1rem;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            background: #ffffff;
            margin-bottom: 1rem;
        }

        .dataset-name {
            font-size: 0.95rem;
            font-weight: 600;
            word-break: break-word;
            margin-bottom: 0.2rem;
        }

        .dataset-status {
            color: #6b7280;
            font-size: 0.8rem;
        }

        /* =========================
           Answer
        ========================= */

        .answer-card {
            padding: 1.25rem 1.4rem;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: #ffffff;
            margin-bottom: 1.5rem;
            line-height: 1.7;
        }

        /* =========================
           History
        ========================= */

        .history-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }

        /* =========================
           Suggestions
        ========================= */

        .suggestion-label {
            color: #6b7280;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
        }

        /* =========================
           Empty State
        ========================= */

        .empty-state {
            padding: 3rem 2rem;
            text-align: center;
            border: 1px dashed #d1d5db;
            border-radius: 14px;
            margin-top: 1rem;
        }

        .empty-state-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.4rem;
        }

        .empty-state-text {
            color: #6b7280;
            font-size: 0.9rem;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Header
# ============================================================

def render_header():
    st.markdown(
        '<div class="app-title">AI Data Analyst</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="app-subtitle">
            Ask questions about your dataset in plain English.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Dataset Summary
# ============================================================

def render_dataset_summary(df):
    if df is None:
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Rows",
            f"{len(df):,}",
        )

    with col2:
        st.metric(
            "Columns",
            len(df.columns),
        )

    with col3:
        st.metric(
            "Missing values",
            f"{df.isna().mean().mean():.1%}",
        )


# ============================================================
# Sidebar
# ============================================================

def render_sidebar(
    uploaded_file=None,
    df=None,
    schema=None,
    unavailable_columns=None,
    history=None,
):
    """
    Render the complete sidebar.

    Returns:
        uploaded_file
    """

    with st.sidebar:

        st.markdown("## AI Data Analyst")

        st.caption(
            "Upload a CSV and ask questions about your data."
        )

        st.divider()

        # ----------------------------------------------------
        # Upload
        # ----------------------------------------------------

        st.markdown("### Dataset")

        new_uploaded_file = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            label_visibility="collapsed",
        )

        if new_uploaded_file is not None:
            uploaded_file = new_uploaded_file

        # ----------------------------------------------------
        # Dataset information
        # ----------------------------------------------------

        if uploaded_file is not None:

            st.markdown(
                f"""
                <div class="sidebar-dataset">
                    <div class="dataset-name">
                        {uploaded_file.name}
                    </div>

                    <div class="dataset-status">
                        Dataset loaded
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            st.caption(
                "Upload a CSV file to get started."
            )

        # ----------------------------------------------------
        # Dataset overview
        # ----------------------------------------------------

        if df is not None:

            st.markdown("### Dataset overview")

            st.caption(
                f"{len(df):,} rows · {len(df.columns)} columns"
            )

            with st.expander("Preview data"):

                st.dataframe(
                    df.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

            # ------------------------------------------------
            # Schema
            # ------------------------------------------------

            if schema:

                with st.expander("Schema"):

                    for column, dtype in schema.items():

                        st.markdown(
                            f"""
                            **{column}**

                            <span style="
                                color:#6b7280;
                                font-size:0.8rem
                            ">
                                {dtype}
                            </span>
                            """,
                            unsafe_allow_html=True,
                        )

            # ------------------------------------------------
            # Unavailable columns
            # ------------------------------------------------

            if unavailable_columns:

                with st.expander(
                    f"Unavailable columns "
                    f"({len(unavailable_columns)})"
                ):

                    for column, reason in (
                        unavailable_columns.items()
                    ):

                        st.markdown(
                            f"""
                            **{column}**

                            <span style="
                                color:#6b7280;
                                font-size:0.8rem
                            ">
                                {reason}
                            </span>
                            """,
                            unsafe_allow_html=True,
                        )

        # ----------------------------------------------------
        # History
        # ----------------------------------------------------

        st.markdown(
            '<div class="history-title">'
            'Previous questions'
            '</div>',
            unsafe_allow_html=True,
        )

        if not history:

            st.caption(
                "No previous questions yet."
            )

        else:

            for index, item in enumerate(
                reversed(history)
            ):

                question = item["question"]

                if len(question) > 55:
                    question = (
                        question[:52] + "..."
                    )

                if st.button(
                    question,
                    key=f"history_{index}",
                    use_container_width=True,
                ):

                    st.session_state.selected_history = item

                    st.rerun()

    return uploaded_file


# ============================================================
# Question Input
# ============================================================

def render_question_section():
    st.markdown(
        '<div class="section-label">'
        'Ask your question'
        '</div>',
        unsafe_allow_html=True,
    )

    question = st.text_area(
        "Question",
        placeholder=(
            "e.g. Which product generated "
            "the highest revenue?"
        ),
        height=110,
        label_visibility="collapsed",
    )

    return question


# ============================================================
# Suggested Questions
# ============================================================

def render_suggestions():
    suggestions = [
        "What is the average value?",
        "Which category has the highest total?",
        "Show the top 5 results.",
    ]

    st.markdown(
        '<div class="suggestion-label">'
        'Try asking'
        '</div>',
        unsafe_allow_html=True,
    )

    columns = st.columns(
        len(suggestions)
    )

    for index, suggestion in enumerate(
        suggestions
    ):

        with columns[index]:

            if st.button(
                suggestion,
                key=f"suggestion_{index}",
                use_container_width=True,
            ):

                st.session_state.selected_question = (
                    suggestion
                )

                st.rerun()


# ============================================================
# Answer
# ============================================================

def render_answer(answer):
    if not answer:
        return

    st.markdown(
        '<div class="section-label">'
        'Analysis result'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="answer-card">
            {answer}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Result
# ============================================================

def render_result(result):
    if isinstance(result, pd.DataFrame):

        st.markdown(
            '<div class="section-label">'
            'Supporting data'
            '</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            result,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.metric(
            label="Result",
            value=result,
        )


# ============================================================
# Previous Analysis
# ============================================================

def render_history_result(history_item):
    st.markdown(
        '<div class="section-label">'
        'Previous analysis'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"**Question:** {history_item['question']}"
    )

    render_answer(
        history_item["answer"]
    )

    result = history_item["result"]

    if isinstance(result, list):

        result_df = pd.DataFrame(result)

        st.markdown(
            '<div class="section-label">'
            'Supporting data'
            '</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True,
        )

        return result_df

    st.metric(
        label="Result",
        value=result,
    )

    return result


# ============================================================
# Empty State
# ============================================================

def render_empty_state():
    st.markdown(
        """
        <div class="empty-state">

            <div class="empty-state-title">
                Start analyzing your data
            </div>

            <div class="empty-state-text">
                Upload a CSV file from the sidebar,
                then ask a question about your dataset.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )