import pandas as pd
import streamlit as st
import altair as alt


def validate_chart_data_types(result, chart_plan):
    chart_type = chart_plan["chart_type"]
    x_column = chart_plan["x"]
    y_column = chart_plan["y"]

    x_is_numeric = pd.api.types.is_numeric_dtype(
        result[x_column]
    )

    y_is_numeric = pd.api.types.is_numeric_dtype(
        result[y_column]
    )

    if chart_type == "bar":
        if not y_is_numeric:
            return False, (
                f"Bar chart requires a numeric y-axis column: "
                f"'{y_column}'."
            )

    elif chart_type == "line":
        if not y_is_numeric:
            return False, (
                f"Line chart requires a numeric y-axis column: "
                f"'{y_column}'."
            )

    elif chart_type == "scatter":
        if not x_is_numeric or not y_is_numeric:
            return False, (
                "Scatter chart requires both x and y columns "
                "to be numeric."
            )

    elif chart_type == "pie":
        if not y_is_numeric:
            return False, (
                f"Pie chart requires a numeric values column: "
                f"'{y_column}'."
            )

    return True, None


def validate_chart_against_result(result, chart_plan):
    if not chart_plan:
        return False, "Missing chart plan."

    if not chart_plan.get("should_plot"):
        return True, None

    if not isinstance(result, pd.DataFrame):
        return False, (
            "The chart requires a DataFrame result."
        )

    if result.empty:
        return False, (
            "Cannot create a chart from an empty result."
        )

    x_column = chart_plan["x"]
    y_column = chart_plan["y"]

    if x_column not in result.columns:
        return False, (
            f"Column '{x_column}' does not exist "
            "in the final result."
        )

    if y_column not in result.columns:
        return False, (
            f"Column '{y_column}' does not exist "
            "in the final result."
        )

    return True, None


def validate_chart_semantics(result, chart_plan):
    chart_type = chart_plan["chart_type"]
    x_column = chart_plan["x"]
    y_column = chart_plan["y"]

    x_series = result[x_column]
    y_series = result[y_column]

    x_is_numeric = pd.api.types.is_numeric_dtype(x_series)
    y_is_numeric = pd.api.types.is_numeric_dtype(y_series)

    x_is_datetime = pd.api.types.is_datetime64_any_dtype(x_series)

    if chart_type == "bar":
        if x_is_numeric:
            return False, (
                "Bar chart x-axis should usually be categorical."
            )

    elif chart_type == "line":
        if not y_is_numeric:
            return False, (
                "Line chart requires a numeric y-axis."
            )

        if x_is_numeric or x_is_datetime:
            if not x_series.is_monotonic_increasing:
                return False, (
                    "Line chart x-axis must be ordered "
                    "from smallest to largest."
                )

    elif chart_type == "scatter":
        if not x_is_numeric or not y_is_numeric:
            return False, (
                "Scatter chart requires numeric x and y columns."
            )

    elif chart_type == "pie":
        if x_is_numeric:
            return False, (
                "Pie chart requires a categorical x-axis."
            )

        if (y_series < 0).any():
            return False, (
                "Pie chart cannot contain negative values."
            )

        if y_series.sum() <= 0:
            return False, (
                "Pie chart requires a positive total."
            )

    return True, None


def render_bar_chart(result, x_column, y_column):
    st.bar_chart(
        result,
        x=x_column,
        y=y_column
    )


def render_line_chart(result, x_column, y_column):
    st.line_chart(
        result,
        x=x_column,
        y=y_column
    )


def render_scatter_chart(result, x_column, y_column):
    st.scatter_chart(
        result,
        x=x_column,
        y=y_column
    )


def render_pie_chart(result, x_column, y_column):
    chart = (
        alt.Chart(result)
        .mark_arc()
        .encode(
            theta=alt.Theta(
                field=y_column,
                type="quantitative"
            ),
            color=alt.Color(
                field=x_column,
                type="nominal"
            ),
            tooltip=[
                x_column,
                y_column
            ]
        )
    )

    st.altair_chart(
        chart,
        use_container_width=True
    )


CHART_REGISTRY = {
    "bar": render_bar_chart,
    "line": render_line_chart,
    "pie": render_pie_chart,
    "scatter": render_scatter_chart
}


def render_chart(result, chart_plan):
    if not chart_plan:
        return

    if not chart_plan.get("should_plot"):
        return

    is_valid, error = validate_chart_against_result(
        result,
        chart_plan
    )

    if not is_valid:
        st.warning(
            f"Chart could not be displayed: {error}"
        )
        return

    chart_type = chart_plan["chart_type"]
    x_column = chart_plan["x"]
    y_column = chart_plan["y"]

    types_valid, type_error = validate_chart_data_types(
        result,
        chart_plan
    )

    if not types_valid:
        st.warning(
            f"Chart could not be displayed: {type_error}"
        )
        return

    semantics_valid, semantic_error = validate_chart_semantics(
        result,
        chart_plan
    )

    if not semantics_valid:
        st.warning(
            f"Chart could not be displayed: {semantic_error}"
        )
        return

    renderer = CHART_REGISTRY.get(chart_type)

    if renderer is None:
        st.warning(
            f"Unsupported chart type: {chart_type}"
        )
        return

    st.subheader("Visualization")

    renderer(
        result,
        x_column,
        y_column
    )