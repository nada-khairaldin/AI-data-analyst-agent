def filter_data(df, column, operator, value):
    if operator == "equals":
        return df[df[column] == value]

    if operator == "not_equals":
        return df[df[column] != value]

    if operator == "greater_than":
        return df[df[column] > value]

    if operator == "less_than":
        return df[df[column] < value]

    if operator == "greater_than_or_equal":
        return df[df[column] >= value]

    if operator == "less_than_or_equal":
        return df[df[column] <= value]

    raise ValueError(f"Unsupported operator: {operator}")


def sort_data(df, column, ascending):
    return df.sort_values(
        by=column,
        ascending=ascending
    )


def limit_results(df, limit):
    return df.head(limit)



def select_columns(df, columns):
    return df[columns]


def aggregate_data(
    df,
    column,
    operation,
    group_by=None
):
    if group_by:
        grouped = df.groupby(group_by)[column]

        if operation == "sum":
            return grouped.sum().reset_index()

        if operation == "mean":
            return grouped.mean().reset_index()

        if operation == "count":
            return grouped.count().reset_index()

        if operation == "min":
            return grouped.min().reset_index()

        if operation == "max":
            return grouped.max().reset_index()

    else:
        series = df[column]

        if operation == "sum":
            return series.sum()

        if operation == "mean":
            return series.mean()

        if operation == "count":
            return series.count()

        if operation == "min":
            return series.min()

        if operation == "max":
            return series.max()

    raise ValueError(
        f"Unsupported aggregation operation: {operation}"
    )


TOOL_REGISTRY = {
    "filter_data": filter_data,
    "aggregate_data": aggregate_data,
    "sort_data": sort_data,
    "select_columns": select_columns,
    "limit_results": limit_results
}


def execute_plan(df, plan):
    current_result = df.copy()

    for step in plan:
        tool_name = step["tool"]

        tool_function = TOOL_REGISTRY[tool_name]

        parameters = {
            key: value
            for key, value in step.items()
            if key != "tool"
        }

        current_result = tool_function(
            current_result,
            **parameters
        )

    return current_result

