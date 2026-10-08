STATUSES = {
    "PENDING": "pending",
    "READY": "ready",
    "NEEDS_CLARIFICATION": "needs_clarification",
    "CANNOT_ANSWER": "cannot_answer",
    "COMPLETED": "completed",
    "FAILED": "failed"
}


ALLOWED_AGENT_STATUSES = {
    STATUSES["READY"],
    STATUSES["NEEDS_CLARIFICATION"],
    STATUSES["CANNOT_ANSWER"]
}


FILTER_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_than_or_equal",
    "less_than_or_equal"
]


AGGREGATION_OPERATIONS = [
    "sum",
    "mean",
    "count",
    "min",
    "max"
]


TOOL_SCHEMAS = {
    "filter_data": {
        "required": ["column", "operator", "value"],
        "column_fields": ["column"],
        "allowed_values": {
            "operator": FILTER_OPERATORS
        },
        "input_type": "dataframe",
        "output_type": "dataframe"
    },

    "aggregate_data": {
        "required": ["column", "operation"],
        "optional": ["group_by"],
        "column_fields": ["column", "group_by"],
        "allowed_values": {
            "operation": AGGREGATION_OPERATIONS
        },
        "input_type": "dataframe",
        "output_type": "dynamic"
    },

    "sort_data": {
        "required": ["column", "ascending"],
        "column_fields": ["column"],
        "types": {
            "ascending": "bool"
        },
        "input_type": "dataframe",
        "output_type": "dataframe"
    },

    "limit_results": {
        "required": ["limit"],
        "column_fields": [],
        "types": {
            "limit": "int"
        },
        "positive_fields": ["limit"],
        "input_type": "dataframe",
        "output_type": "dataframe"
    },

    "select_columns": {
        "required": ["columns"],
        "column_fields": ["columns"],
        "types": {
            "columns": "list"
        },
        "non_empty_fields": ["columns"],
        "input_type": "dataframe",
        "output_type": "dataframe"
    }
}


ALLOWED_CHART_TYPES = {
    "bar",
    "line",
    "pie",
    "scatter"
}


ALLOWED_TOOLS = set(TOOL_SCHEMAS.keys())

