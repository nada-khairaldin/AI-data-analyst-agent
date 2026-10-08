import json
from agent.state import STATUSES

from .schemas import (
    ALLOWED_AGENT_STATUSES,
    STATUSES,
    TOOL_SCHEMAS,
    ALLOWED_CHART_TYPES
)


TYPE_MAP = {
    "bool": bool,
    "int": int,
    "list": list,
    "str": str
}

def validate_analysis_plan(plan, schema):
    if not plan:
        return False, "Analysis plan cannot be empty."

    for step in plan:
        if not isinstance(step, dict):
            return False, "Each analysis step must be a dictionary."

        tool = step.get("tool")

        if tool not in TOOL_SCHEMAS:
            return False, f"Unsupported tool: {tool}"

        tool_schema = TOOL_SCHEMAS[tool]

        # ==========================================
        # Check required fields
        # ==========================================

        for field in tool_schema.get("required", []):
            if field not in step:
                return False, f"{tool} requires '{field}'."

        # ==========================================
        # Check field types
        # ==========================================

        for field, expected_type_name in tool_schema.get(
            "types",
            {}
        ).items():

            if field not in step:
                continue

            value = step[field]

            expected_type = TYPE_MAP[expected_type_name]

            if expected_type_name == "int":
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                ):
                    return False, f"{field} must be an integer."

            elif not isinstance(value, expected_type):
                return False, (
                    f"{field} must be of type "
                    f"{expected_type_name}."
                )

        # ==========================================
        # Check allowed values
        # ==========================================

        for field, allowed_values in tool_schema.get(
            "allowed_values",
            {}
        ).items():

            if field not in step:
                continue

            if step[field] not in allowed_values:
                return False, (
                    f"Invalid value for '{field}': "
                    f"{step[field]}"
                )

        # ==========================================
        # Check positive numeric fields
        # ==========================================

        for field in tool_schema.get(
            "positive_fields",
            []
        ):

            if field not in step:
                continue

            if step[field] <= 0:
                return False, (
                    f"{field} must be greater than zero."
                )

        # ==========================================
        # Check non-empty fields
        # ==========================================

        for field in tool_schema.get(
            "non_empty_fields",
            []
        ):

            if field not in step:
                continue

            if not step[field]:
                return False, (
                    f"{field} cannot be empty."
                )

        # ==========================================
        # Check referenced columns
        # ==========================================

        for field in tool_schema.get(
            "column_fields",
            []
        ):

            if field not in step:
                continue

            value = step[field]

            if isinstance(value, list):
                columns = value
            else:
                columns = [value]

            for column in columns:
                if column not in schema:
                    return False, (
                        f"Unknown column: {column}"
                    )

    # ==========================================
    # Check type flow between tools
    # ==========================================

    type_flow_valid, type_flow_error = validate_plan_types(plan)

    if not type_flow_valid:
        return False, type_flow_error

    return True, None



def validate_agent_output(raw_output, schema):
    try:
        agent_output = json.loads(raw_output)

    except json.JSONDecodeError:
        return False, None, (
            "The model returned invalid JSON."
        )

    if not isinstance(agent_output, dict):
        return False, None, (
            "Agent output must be a dictionary."
        )

    status = agent_output.get("status")

    if status not in ALLOWED_AGENT_STATUSES:
        return False, None, (
            f"Invalid status: {status}"
        )

    if "analysis_plan" not in agent_output:
        return False, None, (
            "analysis_plan is required."
        )

    if not isinstance(
        agent_output["analysis_plan"],
        list
    ):
        return False, None, (
            "analysis_plan must be a list."
        )

    if status == STATUSES["READY"]:
        is_valid, error = validate_analysis_plan(
            agent_output["analysis_plan"],
            schema
        )

        if not is_valid:
            return False, None, error

        chart_plan = agent_output.get("chart_plan")

        chart_is_valid, chart_error = validate_chart_plan(
            chart_plan,
            agent_output["analysis_plan"],
            schema
        )

        if not chart_is_valid:
            return False, None, chart_error
        
    if status in {
        STATUSES["NEEDS_CLARIFICATION"],
        STATUSES["CANNOT_ANSWER"]
    }:
        if agent_output["analysis_plan"]:
            return False, None, (
                f"{status} must have an empty analysis_plan."
            )

        if agent_output.get("chart_plan") is not None:
            return False, None, (
                f"{status} must have chart_plan set to null."
            )

        message = agent_output.get("message")

        if not isinstance(message, str) or not message.strip():
            return False, None, (
                f"{status} requires a message."
            )

    return True, agent_output, None



def get_step_output_type(step):
    tool = step["tool"]

    if tool == "aggregate_data":
        if "group_by" in step:
            return "dataframe"

        return "scalar"

    return TOOL_SCHEMAS[tool]["output_type"]


def validate_plan_types(plan):
    current_type = "dataframe"

    for step in plan:
        tool = step["tool"]

        expected_input = TOOL_SCHEMAS[tool]["input_type"]

        if current_type != expected_input:
            return False, (
                f"{tool} expects input type "
                f"'{expected_input}', "
                f"but received '{current_type}'."
            )

        current_type = get_step_output_type(step)

    return True, None


def get_final_result_columns(plan, schema):
    current_columns = set(schema.keys())

    for step in plan:
        tool = step["tool"]

        if tool == "select_columns":
            current_columns = set(step["columns"])

        elif tool == "aggregate_data":
            group_by = step.get("group_by")

            if group_by:
                current_columns = {
                    group_by,
                    step["column"]
                }
            else:
                return None

    return current_columns


def validate_chart_plan(chart_plan, analysis_plan, schema):
    if not isinstance(chart_plan, dict):
        return False, "Chart plan must be an object."

    should_plot = chart_plan.get("should_plot")

    if not isinstance(should_plot, bool):
        return False, "Chart plan 'should_plot' must be a boolean."

    if not should_plot:
        if (
            chart_plan.get("chart_type") is not None
            or chart_plan.get("x") is not None
            or chart_plan.get("y") is not None
        ):
            return False, (
                "Chart fields must be null when should_plot is false."
            )

        return True, None

    chart_type = chart_plan.get("chart_type")
    x_column = chart_plan.get("x")
    y_column = chart_plan.get("y")

    if chart_type not in ALLOWED_CHART_TYPES:
        return False, (
            f"Unsupported chart type: {chart_type}"
        )

    if not isinstance(x_column, str) or not x_column.strip():
        return False, "Chart x must be a non-empty column name."

    if not isinstance(y_column, str) or not y_column.strip():
        return False, "Chart y must be a non-empty column name."

    final_columns = get_final_result_columns(
        analysis_plan,
        schema
    )

    if final_columns is None:
        return False, (
            "A chart cannot be created from a scalar result."
        )

    if x_column not in final_columns:
        return False, (
            f"Chart x column '{x_column}' "
            "does not exist in the expected final result."
        )

    if y_column not in final_columns:
        return False, (
            f"Chart y column '{y_column}' "
            "does not exist in the expected final result."
        )

    return True, None


def validate_explainer_output(raw_output):
    try:
        output = json.loads(raw_output)

    except json.JSONDecodeError:
        return False, None, (
            "The explainer returned invalid JSON."
        )

    if not isinstance(output, dict):
        return False, None, (
            "Explainer output must be a dictionary."
        )

    summary = output.get("summary")

    if not isinstance(summary, str) or not summary.strip():
        return False, None, (
            "Explainer output requires a non-empty summary."
        )

    return True, summary, None