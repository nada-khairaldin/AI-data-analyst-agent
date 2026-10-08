import pandas as pd
import csv

# ==========================================
# Quality Thresholds
# ==========================================

MISSING_DATASET_THRESHOLD = 0.40
MISSING_COLUMN_THRESHOLD = 0.70

DUPLICATE_WARNING_THRESHOLD = 0.10
DUPLICATE_REJECT_THRESHOLD = 0.50

TYPE_CONVERSION_THRESHOLD = 0.95


# ==========================================
# CSV Loading
# ==========================================

def load_csv(uploaded_file):
    try:
        # Reset file pointer
        uploaded_file.seek(0)

        # Read raw content as text
        content = uploaded_file.getvalue().decode("utf-8")

        # Read only the header row
        reader = csv.reader(content.splitlines())
        headers = next(reader)

        duplicate_columns = [
            column
            for column in set(headers)
            if headers.count(column) > 1
        ]

        if duplicate_columns:
            return None, (
                f"Duplicate column names found: {duplicate_columns}. "
                f"Please rename them and upload the file again."
            )

        # Reset before Pandas reads the file
        uploaded_file.seek(0)

        df = pd.read_csv(uploaded_file)

        return df, None

    except pd.errors.EmptyDataError:
        return None, "The CSV file contains no readable data."

    except pd.errors.ParserError:
        return None, "The file could not be parsed as a valid CSV."

    except UnicodeDecodeError:
        return None, "The file encoding is not supported."

    except Exception:
        return None, "The file could not be read."


# ==========================================
# Missing Values Check
# ==========================================

def check_missing_values(df):
    errors = []
    warnings = []
    unavailable_columns = {}

    overall_missing_ratio = df.isna().mean().mean()
    column_missing_ratios = df.isna().mean()

    # Overall dataset missing values
    if overall_missing_ratio > MISSING_DATASET_THRESHOLD:
        errors.append(
            f"The dataset contains {overall_missing_ratio:.1%} missing values, "
            f"which exceeds the allowed limit of "
            f"{MISSING_DATASET_THRESHOLD:.0%}."
        )

    # Column-level missing values
    for column, ratio in column_missing_ratios.items():

        if ratio > MISSING_COLUMN_THRESHOLD:
            unavailable_columns[column] = (
                f"{ratio:.1%} of values are missing."
            )


            warnings.append(
            f"{ratio:.1%} of values are missing, "
            f"which exceeds the allowed column limit of "
            f"{MISSING_COLUMN_THRESHOLD:.0%}."
            )

    return {
        "errors": errors,
        "warnings": warnings,
        "unavailable_columns": unavailable_columns,
        "overall_missing_ratio": overall_missing_ratio,
        "column_missing_ratios": column_missing_ratios.to_dict()
    }


# ==========================================
# Full DataFrame Validation
# ==========================================

def validate_dataframe(df):
    errors = []
    warnings = []

    # --------------------------------------
    # 1. Empty dataset
    # --------------------------------------

    if df.empty:
        return {
            "errors": ["The dataset contains no data rows."],
            "warnings": [],
            "unavailable_columns": [],
            "overall_missing_ratio": 0,
            "column_missing_ratios": {},
            "duplicate_ratio": 0
        }

    # --------------------------------------
    # 2. Duplicate column names
    # --------------------------------------

    duplicate_columns = (
        df.columns[df.columns.duplicated()]
        .tolist()
    )

    if duplicate_columns:
        errors.append(
            f"Duplicate column names found: {duplicate_columns}"
        )

    # --------------------------------------
    # 3. Missing values
    # --------------------------------------

    missing_report = check_missing_values(df)

    errors.extend(
        missing_report["errors"]
    )

    warnings.extend(
        missing_report["warnings"]
    )

    # --------------------------------------
    # 4. Duplicate rows
    # --------------------------------------

    duplicate_ratio = df.duplicated().mean()

    if duplicate_ratio > DUPLICATE_REJECT_THRESHOLD:

        errors.append(
            f"{duplicate_ratio:.1%} of the rows are duplicates, "
            f"which exceeds the maximum allowed threshold of "
            f"{DUPLICATE_REJECT_THRESHOLD:.0%}."
        )

    elif duplicate_ratio > DUPLICATE_WARNING_THRESHOLD:

        warnings.append(
            f"{duplicate_ratio:.1%} of the rows are duplicates. "
            f"The rows will not be deleted automatically."
        )

    # --------------------------------------
    # Return validation report
    # --------------------------------------

    return {
        "errors": errors,
        "warnings": warnings,
        "unavailable_columns":
            missing_report["unavailable_columns"],

        "overall_missing_ratio":
            missing_report["overall_missing_ratio"],

        "column_missing_ratios":
            missing_report["column_missing_ratios"],

        "duplicate_ratio":
            duplicate_ratio
    }


# ==========================================
# Data Type Normalization
# ==========================================

def normalize_dataframe(df):
    working_df = df.copy()
    conversion_report = {}

    for column in working_df.columns:

        series = working_df[column]

        # Already numeric
        if pd.api.types.is_numeric_dtype(series):
            continue

        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            continue

        # Already boolean
        if pd.api.types.is_bool_dtype(series):
            continue

        non_empty = series.dropna()

        if non_empty.empty:
            continue

        # ==================================
        # Try numeric conversion
        # ==================================

        numeric_conversion = pd.to_numeric(
            non_empty,
            errors="coerce"
        )

        numeric_success_rate = (
            numeric_conversion
            .notna()
            .mean()
        )

        if numeric_success_rate >= TYPE_CONVERSION_THRESHOLD:

            working_df[column] = pd.to_numeric(
                working_df[column],
                errors="coerce"
            )

            conversion_report[column] = {
                "original_type": str(series.dtype),
                "converted_to": "numeric",
                "success_rate": numeric_success_rate
            }

            continue

        # ==================================
        # Try datetime conversion
        # ==================================

        column_name = column.lower()

        date_keywords = [
            "date",
            "time",
            "created",
            "updated",
            "timestamp"
        ]

        looks_like_date_column = any(
            keyword in column_name
            for keyword in date_keywords
        )

        if looks_like_date_column:

            date_conversion = pd.to_datetime(
                non_empty,
                errors="coerce"
            )

            date_success_rate = (
                date_conversion
                .notna()
                .mean()
            )

            if date_success_rate >= TYPE_CONVERSION_THRESHOLD:

                working_df[column] = pd.to_datetime(
                    working_df[column],
                    errors="coerce"
                )

                conversion_report[column] = {
                    "original_type": str(series.dtype),
                    "converted_to": "datetime",
                    "success_rate": date_success_rate
                }

    return working_df, conversion_report


# ==========================================
# Complete Preparation Process
# ==========================================

def prepare_dataframe(df):

    # --------------------------------------
    # 1. Full validation before normalization
    # --------------------------------------

    initial_validation = validate_dataframe(df)

    if initial_validation["errors"]:

        return {
            "working_df": None,
            "errors": initial_validation["errors"],
            "warnings": initial_validation["warnings"],
            "unavailable_columns":
                initial_validation["unavailable_columns"],
            "conversions": {}
        }

    # --------------------------------------
    # 2. Normalize data types
    # --------------------------------------

    working_df, conversions = normalize_dataframe(df)

    # --------------------------------------
    # 3. Re-check missing values only
    # --------------------------------------

    final_missing_report = check_missing_values(
        working_df
    )

    # Keep initial warnings that are not
    # related to missing values
    duplicate_warnings = []

    duplicate_ratio = initial_validation["duplicate_ratio"]

    if (
        duplicate_ratio > DUPLICATE_WARNING_THRESHOLD
        and
        duplicate_ratio <= DUPLICATE_REJECT_THRESHOLD
    ):
        duplicate_warnings.append(
            f"{duplicate_ratio:.1%} of the rows are duplicates. "
            f"The rows will not be deleted automatically."
        )

    return {
        "working_df": working_df,

        "errors":
            final_missing_report["errors"],

        "warnings":
            duplicate_warnings
            + final_missing_report["warnings"],

        "unavailable_columns":
            final_missing_report["unavailable_columns"],

        "conversions":
            conversions
    }


def validate_question(question):
    if not question or not question.strip():
        return False, "Please enter a question."

    return True, None


