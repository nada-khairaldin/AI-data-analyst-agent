def get_schema(df):
    return {
        column: str(dtype)
        for column, dtype in df.dtypes.items()
    }

