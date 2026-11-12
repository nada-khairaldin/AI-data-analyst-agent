"""ORM rows -> the exact JSON shapes in API_CONTRACT.md.

Kept out of the routers so the wire format has one definition: endpoint 3
nests the same conversation object that endpoint 8 returns flat, and endpoint
11's message must be byte-identical to endpoint 10's.
"""

from app.presenters import (
    chart_title,
    format_bytes,
    format_percent,
    format_relative,
    quality_label,
    render_plan,
)


def conversation_summary(conversation) -> dict:
    """The sidebar object, shared by endpoints 3, 8, 9 and 14."""
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "date": format_relative(conversation.last_message_at),
        "messageCount": conversation.message_count or 0,
    }


def dataset_detail(dataset) -> dict:
    """One element of endpoint 3, and the whole of endpoints 2 and 4."""
    conversations = sorted(
        dataset.conversations or [],
        key=lambda c: c.last_message_at,
        reverse=True,
    )
    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "rowCount": dataset.row_count,
        "colCount": dataset.column_count,
        "size": format_bytes(dataset.size_bytes),
        "missingRate": format_percent(dataset.missing_rate),
        "duplicateRate": format_percent(dataset.duplicate_rate),
        "status": dataset.status,
        "conversations": [conversation_summary(c) for c in conversations],
    }


def report_detail(dataset, report) -> dict:
    """Endpoint 5. excluded/converted counts are derived from the stored
    checks so the card and the report can never disagree."""
    excluded = 0
    converted = 0
    for check in report.checks or []:
        excluded += len(check.get("excludedColumns") or [])
        converted += len(check.get("conversions") or [])

    score = float(report.overall_missing_ratio or 0)
    score = max(0.0, 1.0 - score)

    return {
        "datasetId": str(dataset.id),
        "checksCompleted": report.checks_completed,
        "noticeCount": report.notice_count,
        "qualityScore": format_percent(score),
        "qualityLabel": quality_label(score),
        "excludedColumnCount": excluded,
        "convertedColumnCount": converted,
        "checks": report.checks or [],
    }


def column_detail(column) -> dict:
    """Endpoint 6. Excluded columns are listed with available:false rather
    than omitted — the report promises they stay in the dataset."""
    return {
        "name": column.name,
        "dtype": column.dtype,
        "available": bool(column.is_available),
        "missingRate": format_percent(column.missing_ratio),
        "exclusionReason": column.exclusion_reason,
    }


def message_detail(message) -> dict:
    """Endpoint 10's message object, reused verbatim by endpoint 11.

    A user message carries only role and content. An agent message always
    carries every key the UI guards on, so the shape never varies by status.
    """
    if message.role == "user":
        return {"role": "user", "content": message.content}

    plan = message.plan_display
    chart = message.chart_plan or {}
    show_chart = bool(chart.get("should_plot")) and message.result_data is not None

    return {
        "role": "agent",
        "status": message.status,
        "content": message.content,
        "condensedQuestion": message.condensed_question,
        "showChart": show_chart,
        "chartTitle": chart_title(chart, message.analysis_plan) if show_chart else None,
        "resultData": message.result_data,
        "resultKind": message.result_kind,
        "plan": plan,
    }


def search_result(conversation, dataset_name) -> dict:
    """Endpoint 14 adds the dataset to the sidebar object."""
    item = conversation_summary(conversation)
    item["datasetId"] = str(conversation.dataset_id)
    item["datasetName"] = dataset_name
    return item


def plan_for_message(question, analysis_plan):
    """None for clarification and cannot_answer turns, which have no plan."""
    if not analysis_plan:
        return None
    return render_plan(question, analysis_plan)
