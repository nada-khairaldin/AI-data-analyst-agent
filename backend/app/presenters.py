"""Every string the API hands to the UI pre-formatted, in one place.

The contract returns ``size``, ``missingRate``, ``duplicateRate``,
``qualityScore``, ``successRate`` and ``date`` as **formatted strings**, not
numbers, because the mock the frontend was built against used strings
(``'45 KB'``, ``'2.1%'``, ``'2 hours ago'``) and the JSX prints them verbatim.
See API_CONTRACT.md "Suggested changes S1/S2".

Keeping the formatting here rather than in the routers matters for one
specific reason: the same number is rendered in several places — the sidebar,
the overview header, the quality card and the preprocessing report all show
the missing rate — and a second implementation is how two parts of one screen
start disagreeing about the same dataset.

The database stores real numbers (``numeric(6,5)``), so sorting and
thresholds still work on the values; only the presentation is stringly typed.
"""

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------


def format_bytes(size) -> str:
    """``45678`` -> ``"45 KB"``.

    Matches the mock's ``'45 KB'``: whole kilobytes, one decimal for
    megabytes. Uses 1024, so a 5 MB upload limit and the size shown to the
    user agree with each other.
    """
    if size is None:
        return "0 B"

    size = float(size)
    if size < 1024:
        return f"{int(size)} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def format_percent(ratio, decimals: int = 1) -> str:
    """``0.0210`` -> ``"2.1%"``.

    Takes a RATIO (0-1), not a percentage, because that is what
    ``validation.py`` produces and what the database stores. Passing 2.1 here
    by mistake would render "210.0%", which is why the argument name is
    ``ratio``.
    """
    if ratio is None:
        return "0.0%"
    return f"{float(ratio) * 100:.{decimals}f}%"


def format_success_rate(ratio) -> str:
    """``1.0`` -> ``"100% converted"``; ``0.997`` -> ``"99.7% converted"``.

    The JSX prints this verbatim, including the word. A whole number loses the
    decimal because "100.0% converted" reads like a measurement error.
    """
    if ratio is None:
        return "0% converted"

    value = float(ratio) * 100
    if abs(value - round(value)) < 0.05:
        return f"{round(value)}% converted"
    return f"{value:.1f}% converted"


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

# Defined in API_CONTRACT.md endpoint 5 so the number is not invented a second
# time in the UI, which is where it currently lives as a hardcoded "97.9%".
QUALITY_GOOD = 0.95
QUALITY_FAIR = 0.85


def quality_score(overall_missing_ratio) -> float:
    """``1 - overall_missing_ratio``, per the contract.

    Deliberately simple and deliberately written down. A richer score
    (weighing duplicates, excluded columns, conversion failures) would be
    defensible, but it has to be defined *somewhere* or the UI will invent its
    own and the two will disagree.
    """
    return max(0.0, min(1.0, 1.0 - float(overall_missing_ratio or 0.0)))


def quality_label(score) -> str:
    score = float(score)
    if score >= QUALITY_GOOD:
        return "Good"
    if score >= QUALITY_FAIR:
        return "Fair"
    return "Poor"


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def format_relative(moment, *, now=None) -> str:
    """``datetime`` -> ``"2 hours ago"``, matching the mock's strings exactly.

    Rendered on the server, not the client, because the mock shipped these as
    literals and the sidebar prints them straight out (S2). The cost is that a
    page left open goes stale; the alternative is a frontend change this
    contract is trying to avoid.

    Naive datetimes are assumed UTC. Every timestamp in this schema is
    ``timestamptz``, so that only arises in tests.
    """
    if moment is None:
        return "Just now"

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    seconds = (now - moment).total_seconds()

    # A clock skew between the app and the database should not produce
    # "in -3 seconds"; anything in the future reads as just now.
    if seconds < 60:
        return "Just now"

    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"

    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

TITLE_LIMIT = 25
DEFAULT_TITLE = "New Conversation"


def title_from_question(question: str) -> str:
    """The sidebar label, auto-named from the first question.

    Mirrors the mock's ``text.substring(0, 25) + '...'`` (App.jsx:169) so the
    server-rendered label is identical to what the UI used to produce for
    itself. The ellipsis is only added when something was actually cut.
    """
    text = " ".join((question or "").split())
    if not text:
        return DEFAULT_TITLE
    if len(text) <= TITLE_LIMIT:
        return text
    return text[:TITLE_LIMIT] + "..."


# ---------------------------------------------------------------------------
# Rendering a plan for the UI
# ---------------------------------------------------------------------------

_OPERATION_WORDS = {
    "sum": "SUM",
    "mean": "AVERAGE",
    "count": "COUNT",
    "min": "MINIMUM",
    "max": "MAXIMUM",
}

_OPERATOR_WORDS = {
    "equals": "=",
    "not_equals": "!=",
    "greater_than": ">",
    "less_than": "<",
    "greater_than_or_equal": ">=",
    "less_than_or_equal": "<=",
}


def plan_steps(analysis_plan) -> list[str]:
    """Turn the raw tool list into the English sentences the UI shows.

    The UI must stay dumb: it renders these strings and nothing else. Doing
    this on the server means the wording can change without a frontend
    deploy, and means the explainer and the plan panel describe the same
    analysis in the same words.
    """
    steps = []
    for step in analysis_plan or []:
        tool = step.get("tool")

        if tool == "filter_data":
            operator = _OPERATOR_WORDS.get(step.get("operator"), step.get("operator"))
            steps.append(
                f"Filter rows where {step.get('column')} {operator} "
                f"{step.get('value')}"
            )

        elif tool == "aggregate_data":
            word = _OPERATION_WORDS.get(step.get("operation"), step.get("operation"))
            group_by = step.get("group_by")
            if group_by:
                keys = group_by if isinstance(group_by, list) else [group_by]
                steps.append(f"Group by {' and '.join(str(k) for k in keys)}")
            steps.append(f"Calculate {word} of {step.get('column')}")

        elif tool == "sort_data":
            direction = "ascending" if step.get("ascending") else "descending"
            steps.append(f"Sort by {step.get('column')} ({direction})")

        elif tool == "select_columns":
            columns = ", ".join(step.get("columns") or [])
            steps.append(f"Keep only the columns {columns}")

        elif tool == "limit_results":
            limit = step.get("limit")
            steps.append(f"Take top {limit} result{'s' if limit != 1 else ''}")

        else:
            # Unknown tools cannot reach here — validators.py rejects them
            # before execution — but a plan replayed from an older row might
            # contain one, and a readable fallback beats a KeyError.
            steps.append(str(tool))

    return steps


def plan_filters(analysis_plan) -> str:
    """``"None"``, or ``"Country = FR"``, matching the mock and PROJECT_PLAN §5."""
    parts = []
    for step in analysis_plan or []:
        if step.get("tool") != "filter_data":
            continue
        operator = _OPERATOR_WORDS.get(step.get("operator"), step.get("operator"))
        parts.append(f"{step.get('column')} {operator} {step.get('value')}")

    return ", ".join(parts) if parts else "None"


def plan_columns_used(analysis_plan) -> list[str]:
    """Every column the plan touches, in first-mention order.

    Order is preserved rather than sorted so the list reads in the order the
    analysis actually used them, which is what makes it skimmable next to the
    steps.
    """
    seen = []
    for step in analysis_plan or []:
        for field in ("column", "group_by"):
            value = step.get(field)
            # group_by may be a list for a multi-key aggregation.
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str) and item not in seen:
                    seen.append(item)
        for value in step.get("columns") or []:
            if value not in seen:
                seen.append(value)
    return seen


def render_plan(question: str, analysis_plan) -> dict:
    """The ``plan`` object from API_CONTRACT.md endpoints 10 and 11."""
    return {
        "question": question,
        "steps": plan_steps(analysis_plan),
        "columnsUsed": plan_columns_used(analysis_plan),
        "filters": plan_filters(analysis_plan),
    }


def chart_title(chart_plan, analysis_plan) -> str | None:
    """A caption for the chart, derived rather than asked of the model.

    The planner is not asked for a title: one more free-text field is one more
    thing to validate, and the axes plus the aggregation already say what the
    chart shows.
    """
    if not chart_plan or not chart_plan.get("should_plot"):
        return None

    x = chart_plan.get("x")
    y = chart_plan.get("y")

    operation = None
    limit = None
    for step in analysis_plan or []:
        if step.get("tool") == "aggregate_data":
            operation = step.get("operation")
        elif step.get("tool") == "limit_results":
            limit = step.get("limit")

    word = {"sum": "total", "mean": "average", "count": "number of"}.get(operation)
    measure = f"{word} {y}" if word else y

    title = f"{measure} by {x}"
    if limit:
        title = f"Top {limit} {x} by {measure}"

    return title[:1].upper() + title[1:]


# ---------------------------------------------------------------------------
# JSON safety
# ---------------------------------------------------------------------------


def to_jsonable(value):
    """One pandas/numpy scalar -> something json.dumps accepts.

    Needed in two places that both write JSON the browser must parse: the
    preview rows and a message's result_data (which also goes into a jsonb
    column, where a Timestamp is not a valid value).

    Handles, in order: None; NaN/NaT (-> null, because NaN is not valid JSON
    and a strict parser rejects it); datetimes and dates (-> ISO 8601 string);
    numpy scalars (-> their Python equivalent); anything already primitive.
    """
    if value is None:
        return None

    # NaN is the only value that is not equal to itself. Catches NaN, NaT and
    # pandas.NA without importing pandas here.
    try:
        if value != value:
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value

    if isinstance(value, float) and (value in (float("inf"), float("-inf"))):
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return to_jsonable(value.item())
        except (ValueError, AttributeError):
            return str(value)

    if isinstance(value, (str, int, float)):
        return value

    return str(value)
