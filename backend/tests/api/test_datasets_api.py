"""API tests for the dataset endpoints (phase B1)."""

import uuid


# ---------------------------------------------------------------------------
# Session scoping
# ---------------------------------------------------------------------------


async def test_a_missing_session_header_is_rejected(client):
    response = await client.get("/api/datasets")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


async def test_a_non_uuid_session_header_is_rejected(client):
    response = await client.get("/api/datasets", headers={"X-Session-Id": "not-a-uuid"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


async def test_an_unknown_session_sees_an_empty_list_not_an_error(client):
    """A read must not create a session row, and must not 404."""
    response = await client.get(
        "/api/datasets", headers={"X-Session-Id": str(uuid.uuid4())}
    )

    assert response.status_code == 200
    assert response.json() == {"datasets": []}


async def test_a_session_cannot_see_another_sessions_dataset(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    other = {"X-Session-Id": str(uuid.uuid4())}
    assert (await client.get("/api/datasets", headers=other)).json() == {"datasets": []}
    # 404 rather than 403: telling the two apart would confirm that another
    # session's id exists.
    assert (await client.get(f"/api/datasets/{dataset_id}", headers=other)).status_code == 404


# ---------------------------------------------------------------------------
# Upload — endpoint 2
# ---------------------------------------------------------------------------


async def test_upload_returns_the_contract_shape(upload):
    response = await upload()
    body = response.json()

    assert response.status_code == 201
    assert set(body) == {
        "id",
        "name",
        "rowCount",
        "colCount",
        "size",
        "missingRate",
        "duplicateRate",
        "status",
        "conversations",
    }
    assert body["name"] == "orders.csv"
    assert body["status"] == "ready"
    assert body["conversations"] == []


async def test_upload_reports_the_real_row_and_column_counts(upload):
    body = (await upload()).json()

    # 1,500 rows (1,305 unique + 195 duplicates) and 11 columns: the 9 from
    # the CSV, including the excluded one, plus OrderDate_year and
    # OrderDate_month derived at upload.
    assert body["rowCount"] == 1500
    assert body["colCount"] == 11


async def test_upload_preformats_size_and_rates_as_strings(upload):
    body = (await upload()).json()

    assert body["size"].endswith(("B", "KB", "MB"))
    assert body["missingRate"].endswith("%")
    assert body["duplicateRate"].endswith("%")


async def test_a_dirty_but_acceptable_dataset_is_accepted(upload):
    """orders.csv has an excluded column, a converted column and duplicates."""
    assert (await upload()).status_code == 201


async def test_bad_csv_is_rejected_with_the_rejection_fields(upload):
    response = await upload("bad.csv")
    error = response.json()["error"]

    assert response.status_code == 422
    assert error["code"] == "DATASET_REJECTED"
    details = error["details"]
    # These map 1:1 onto DatasetRejected.jsx props.
    assert details["filename"] == "bad.csv"
    assert details["fileSize"].endswith(("B", "KB", "MB"))
    assert details["missingRate"].endswith("%")
    assert details["maxAllowed"] == "40%"
    assert details["reasons"]
    assert any("missing" in reason for reason in details["reasons"])


async def test_a_non_csv_is_rejected(client, headers):
    response = await client.post(
        "/api/datasets",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE"


async def test_an_empty_file_is_rejected(client, headers):
    response = await client.post(
        "/api/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
        headers=headers,
    )

    assert response.status_code == 422


async def test_an_oversized_file_is_rejected_before_parsing(client, headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 100, raising=False)
    payload = b"a,b\n" + b"1,2\n" * 200

    response = await client.post(
        "/api/datasets",
        files={"file": ("big.csv", payload, "text/csv")},
        headers=headers,
    )
    error = response.json()["error"]

    assert response.status_code == 413
    assert error["code"] == "FILE_TOO_LARGE"
    assert error["details"]["maxAllowed"]


async def test_too_many_rows_is_rejected_after_parsing(client, headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_dataset_rows", 3, raising=False)
    payload = b"a,b\n" + b"1,2\n" * 10

    response = await client.post(
        "/api/datasets",
        files={"file": ("many.csv", payload, "text/csv")},
        headers=headers,
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_MANY_ROWS"


async def test_the_dataset_cap_is_enforced(client, headers, monkeypatch, samples):
    from app.config import settings

    monkeypatch.setattr(settings, "max_datasets_per_session", 2, raising=False)
    content = (samples / "customers.csv").read_bytes()

    for _ in range(2):
        assert (
            (await client.post(
                "/api/datasets",
                files={"file": ("customers.csv", content, "text/csv")},
                headers=headers,
            )).status_code
            == 201
        )

    response = await client.post(
        "/api/datasets",
        files={"file": ("customers.csv", content, "text/csv")},
        headers=headers,
    )
    error = response.json()["error"]

    assert response.status_code == 409
    assert error["code"] == "DATASET_LIMIT_REACHED"
    assert error["details"] == {"current": 2, "maximum": 2}


# ---------------------------------------------------------------------------
# Persistence — the point of the whole phase
# ---------------------------------------------------------------------------


async def test_a_dataset_survives_a_new_client(client, upload, headers, engine):
    """The old /api/upload kept frames in a module-level dict, so every
    restart lost them. This is the regression test for that.

    A second client over the same app is a fresh request path with no
    in-process state carried over; only the database and the object store can
    satisfy the read.
    """
    dataset_id = (await upload()).json()["id"]

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as fresh:
        response = await fresh.get(f"/api/datasets/{dataset_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == dataset_id


async def test_the_object_is_written_to_storage(upload, fake_store):
    dataset_id = (await upload()).json()["id"]

    assert f"datasets/{dataset_id}.parquet" in fake_store


# ---------------------------------------------------------------------------
# List and get — endpoints 3 and 4
# ---------------------------------------------------------------------------


async def test_list_returns_newest_first(client, headers, samples):
    for name in ("customers.csv", "orders.csv"):
        await client.post(
            "/api/datasets",
            files={"file": (name, (samples / name).read_bytes(), "text/csv")},
            headers=headers,
        )

    names = [d["name"] for d in (await client.get("/api/datasets", headers=headers)).json()["datasets"]]

    assert names == ["orders.csv", "customers.csv"]


async def test_get_one_dataset(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}", headers=headers)).json()

    assert body["id"] == dataset_id
    assert "conversations" in body


async def test_an_unknown_dataset_is_404(client, headers):
    response = await client.get(f"/api/datasets/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Report — endpoint 5
# ---------------------------------------------------------------------------


async def test_the_report_has_six_checks_in_order(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/report", headers=headers)).json()

    assert body["checksCompleted"] == 6
    assert [c["order"] for c in body["checks"]] == [1, 2, 3, 4, 5, 6]
    assert all(c["level"] in {"success", "warning", "info", "error"} for c in body["checks"])


async def test_the_report_names_the_excluded_column(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/report", headers=headers)).json()
    excluded = [
        column
        for check in body["checks"]
        for column in check.get("excludedColumns") or []
    ]

    assert body["excludedColumnCount"] == 1
    assert excluded[0]["name"] == "customer_phone"
    assert "missing" in excluded[0]["reason"]


async def test_the_report_lists_the_conversions(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/report", headers=headers)).json()
    conversions = [
        conversion
        for check in body["checks"]
        for conversion in check.get("conversions") or []
    ]
    names = {c["name"] for c in conversions}

    # quantity arrives as text, OrderDate as a date-like string.
    assert {"quantity", "OrderDate"} <= names
    assert all(c["successRate"].endswith("converted") for c in conversions)


async def test_the_report_carries_a_quality_score_and_label(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/report", headers=headers)).json()

    assert body["qualityScore"].endswith("%")
    assert body["qualityLabel"] in {"Good", "Fair", "Poor"}


# ---------------------------------------------------------------------------
# Columns — endpoint 6
# ---------------------------------------------------------------------------


async def test_columns_include_the_excluded_one(client, upload, headers):
    """available:false rather than omitted — the report promises the column
    stays in the dataset."""
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/columns", headers=headers)).json()
    by_name = {c["name"]: c for c in body["columns"]}

    assert len(body["columns"]) == 11
    assert by_name["customer_phone"]["available"] is False
    assert by_name["customer_phone"]["exclusionReason"]
    assert by_name["Product"]["available"] is True
    assert by_name["Product"]["exclusionReason"] is None


async def test_columns_keep_their_original_order(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/columns", headers=headers)).json()

    assert [c["name"] for c in body["columns"]][:3] == [
        "OrderID",
        "OrderDate",
        "Product",
    ]


async def test_column_dtypes_are_post_normalisation(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/columns", headers=headers)).json()
    by_name = {c["name"]: c for c in body["columns"]}

    # quantity was text in the CSV and is numeric after normalisation.
    assert by_name["quantity"]["dtype"].startswith("float")
    assert by_name["OrderDate"]["dtype"].startswith("datetime")


# ---------------------------------------------------------------------------
# Preview — endpoint 7
# ---------------------------------------------------------------------------


async def test_preview_returns_ordered_columns_and_rows(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(
        f"/api/datasets/{dataset_id}/preview?limit=3", headers=headers
    )).json()

    assert body["columns"][0] == "OrderID"
    assert len(body["rows"]) == 3
    assert body["totalRows"] == 1500
    assert set(body["rows"][0]) == set(body["columns"])


async def test_preview_defaults_to_five_rows(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/preview", headers=headers)).json()

    assert len(body["rows"]) == 5


async def test_preview_limit_is_capped(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    response = await client.get(
        f"/api/datasets/{dataset_id}/preview?limit=5000", headers=headers
    )

    assert response.status_code == 400


async def test_preview_serialises_missing_values_as_null(client, upload, headers):
    """customer_phone is ~74% missing, so some preview cell must be null."""
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(
        f"/api/datasets/{dataset_id}/preview?limit=40", headers=headers
    )).json()
    phones = [row["customer_phone"] for row in body["rows"]]

    assert None in phones


async def test_preview_is_json_serialisable_for_dates(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.get(f"/api/datasets/{dataset_id}/preview", headers=headers)).json()

    assert isinstance(body["rows"][0]["OrderDate"], str)


# ---------------------------------------------------------------------------
# Delete — endpoint 13
# ---------------------------------------------------------------------------


async def test_delete_removes_the_dataset_and_its_object(client, upload, headers, fake_store):
    dataset_id = (await upload()).json()["id"]
    key = f"datasets/{dataset_id}.parquet"
    assert key in fake_store

    response = await client.delete(f"/api/datasets/{dataset_id}", headers=headers)

    assert response.status_code == 204
    assert key not in fake_store
    assert (await client.get(f"/api/datasets/{dataset_id}", headers=headers)).status_code == 404


async def test_delete_frees_a_slot_against_the_cap(client, upload, headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_datasets_per_session", 1, raising=False)
    dataset_id = (await upload()).json()["id"]
    assert (await upload()).status_code == 409

    await client.delete(f"/api/datasets/{dataset_id}", headers=headers)

    assert (await upload()).status_code == 201


async def test_deleting_another_sessions_dataset_is_404(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    response = await client.delete(
        f"/api/datasets/{dataset_id}", headers={"X-Session-Id": str(uuid.uuid4())}
    )

    assert response.status_code == 404
