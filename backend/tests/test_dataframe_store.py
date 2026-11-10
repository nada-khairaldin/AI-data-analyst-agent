"""Tests for dataframe_store.py (phase A7).

The S3 client is replaced with a dict-backed fake. A suite that writes to the
real bucket cannot be run offline, costs requests, and — because Neon's
DeleteObject is a soft delete that does not reclaim storage — would leave
rubbish behind on every run that it has no way to clean up.

The live round-trip WAS run by hand against the real bucket and is recorded in
the commit: dtypes identical across save/load (str, int64, float64, bool,
datetime64[us]), NaN/None/NaT preserved, no phantom index column, LRU eviction
at 3, and ObjectMissing raised after a delete.
"""

import io
import uuid

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from app.services import dataframe_store as store


class FakeS3:
    """A dict standing in for the bucket, with botocore-shaped errors."""

    def __init__(self):
        self.objects = {}
        self.calls = []

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.calls.append(("put", Key))
        self.objects[Key] = Body
        return {}

    def get_object(self, Bucket, Key):
        self.calls.append(("get", Key))
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
            )
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.calls.append(("delete", Key))
        self.objects.pop(Key, None)
        return {}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "not found"}}, "HeadObject"
            )
        return {}

    def head_bucket(self, Bucket):
        return {}


@pytest.fixture
def fake(monkeypatch):
    client = FakeS3()
    monkeypatch.setattr(store, "get_client", lambda: client)
    store.clear_cache()
    yield client
    store.clear_cache()


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "Product": ["Laptop", "Mouse", "Keyboard"],
            "Quantity": pd.Series([10, 5, 7], dtype="int64"),
            "Price": pd.Series([1000.5, 25.0, 50.25], dtype="float64"),
        }
    )


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------


def test_object_key_is_stable_and_prefixed():
    dataset_id = uuid.UUID("89de6dcb-4237-439d-b432-e25b5a29021e")

    assert (
        store.object_key_for(dataset_id)
        == "datasets/89de6dcb-4237-439d-b432-e25b5a29021e.parquet"
    )


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


def test_save_then_load_preserves_values_and_dtypes(fake, frame):
    """The entire justification for Parquet over CSV.

    If dtypes did not survive, loading would re-run type inference and the
    same question could get a different answer on a later request.
    """
    key, size = store.save(uuid.uuid4(), frame)
    store.clear_cache()

    loaded = store.load(key)

    assert size > 0
    assert loaded.dtypes.equals(frame.dtypes)
    assert loaded.equals(frame)


def test_save_does_not_write_the_index(fake, frame):
    """A written index comes back as __index_level_0__ and leaks into the
    schema the planner is shown."""
    key, _ = store.save(uuid.uuid4(), frame)
    store.clear_cache()

    assert "__index_level_0__" not in store.load(key).columns


def test_save_returns_the_real_byte_size(fake, frame):
    """dataset_files.byte_size must be the stored size, not the frame's."""
    key, size = store.save(uuid.uuid4(), frame)

    assert size == len(fake.objects[key])


def test_missing_values_survive_the_round_trip(fake):
    original = pd.DataFrame(
        {
            "text": ["a", None, "c"],
            "number": [1.0, None, 3.0],
            "when": pd.to_datetime(["2024-01-01", None, "2024-03-01"]),
        }
    )

    key, _ = store.save(uuid.uuid4(), original)
    store.clear_cache()
    loaded = store.load(key)

    assert loaded["text"].isna().sum() == 1
    assert loaded["number"].isna().sum() == 1
    assert loaded["when"].isna().sum() == 1


# ---------------------------------------------------------------------------
# The cache
# ---------------------------------------------------------------------------


def test_a_second_load_does_not_hit_storage(fake, frame):
    key, _ = store.save(uuid.uuid4(), frame)
    store.clear_cache()

    store.load(key)
    gets_after_first = [c for c in fake.calls if c[0] == "get"]
    store.load(key)
    gets_after_second = [c for c in fake.calls if c[0] == "get"]

    assert len(gets_after_first) == 1
    assert len(gets_after_second) == 1, "the second load should be cached"


def test_load_returns_the_cached_object_not_a_copy(fake, frame):
    """Pins the documented contract, so it is explicit rather than incidental.

    Copying a 100k-row frame per request would defeat the cache. The price is
    that callers must not mutate the result; execute_plan() copies first, so
    nothing in this codebase does.
    """
    key, _ = store.save(uuid.uuid4(), frame)
    store.clear_cache()

    assert store.load(key) is store.load(key)


def test_save_populates_the_cache(fake, frame):
    key, _ = store.save(uuid.uuid4(), frame)

    assert key in store.cache_info()["keys"]


def test_the_cache_evicts_the_least_recently_used(fake, monkeypatch):
    monkeypatch.setattr(store.settings, "dataframe_cache_size", 3, raising=False)
    store.clear_cache()

    keys = [store.save(uuid.uuid4(), pd.DataFrame({"n": [i]}))[0] for i in range(4)]
    info = store.cache_info()

    assert info["size"] == 3
    assert keys[0] not in info["keys"], "the oldest entry should have been evicted"
    assert keys[-1] in info["keys"]


def test_reading_an_entry_makes_it_recently_used(fake, monkeypatch):
    """Otherwise it is a FIFO queue, not an LRU cache."""
    monkeypatch.setattr(store.settings, "dataframe_cache_size", 2, raising=False)
    store.clear_cache()

    first, _ = store.save(uuid.uuid4(), pd.DataFrame({"n": [1]}))
    second, _ = store.save(uuid.uuid4(), pd.DataFrame({"n": [2]}))

    store.load(first)  # refresh the oldest
    third, _ = store.save(uuid.uuid4(), pd.DataFrame({"n": [3]}))

    keys = store.cache_info()["keys"]
    assert first in keys, "the refreshed entry must survive"
    assert second not in keys, "the genuinely stale entry should be evicted"
    assert third in keys


def test_an_overwrite_does_not_serve_the_old_frame(fake):
    dataset_id = uuid.uuid4()
    store.save(dataset_id, pd.DataFrame({"n": [1]}))

    key, _ = store.save(dataset_id, pd.DataFrame({"n": [2]}))

    assert store.load(key)["n"].tolist() == [2]


def test_delete_invalidates_the_cache(fake, frame):
    """Without this, a re-upload reusing the key would serve stale data."""
    key, _ = store.save(uuid.uuid4(), frame)
    assert key in store.cache_info()["keys"]

    store.delete(key)

    assert key not in store.cache_info()["keys"]


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_a_missing_object_raises_object_missing(fake):
    """The recoverable half of the delete ordering in PLAN §4.

    A dataset_files row pointing at a vanished object must say "re-upload",
    not return an empty result that looks like a legitimate answer.
    """
    with pytest.raises(store.ObjectMissing) as caught:
        store.load("datasets/not-a-real-object.parquet")

    assert "re-upload" in str(caught.value).lower()


def test_object_missing_is_a_storage_error():
    """So a caller that only knows about StorageError still catches it."""
    assert issubclass(store.ObjectMissing, store.StorageError)


def test_other_client_errors_become_storage_error(fake, monkeypatch):
    def boom(**kwargs):
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "nope"}}, "GetObject"
        )

    monkeypatch.setattr(fake, "get_object", boom)

    with pytest.raises(store.StorageError) as caught:
        store.load("datasets/whatever.parquet")

    assert not isinstance(caught.value, store.ObjectMissing)
    assert "AccessDenied" in str(caught.value)


def test_corrupt_bytes_raise_a_clear_storage_error(fake):
    fake.objects["datasets/corrupt.parquet"] = b"this is not parquet"

    with pytest.raises(store.StorageError) as caught:
        store.load("datasets/corrupt.parquet")

    assert "not readable Parquet" in str(caught.value)


def test_delete_never_raises(fake, monkeypatch):
    """A failed delete must not abort dataset deletion.

    The caller removes the object before the row, and the user asked for the
    dataset to be gone. A row pointing at a live object is recoverable; an
    object with no row is invisible.
    """

    def boom(**kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")

    monkeypatch.setattr(fake, "delete_object", boom)

    assert store.delete("datasets/whatever.parquet") is False


def test_delete_reports_success(fake, frame):
    key, _ = store.save(uuid.uuid4(), frame)

    assert store.delete(key) is True


def test_exists(fake, frame):
    key, _ = store.save(uuid.uuid4(), frame)

    assert store.exists(key) is True
    assert store.exists("datasets/nope.parquet") is False


def test_missing_configuration_is_its_own_error(monkeypatch):
    """A deployment mistake, not a transient failure — retrying never helps."""
    store.reset_client()
    monkeypatch.setattr(store.settings, "aws_endpoint_url_s3", "", raising=False)

    with pytest.raises(store.StorageNotConfigured) as caught:
        store.get_client()

    assert "AWS_ENDPOINT_URL_S3" in str(caught.value)
    store.reset_client()


def test_error_descriptions_never_leak_credentials(fake, monkeypatch):
    """storageDetail and log lines are the one place a secret could escape."""
    monkeypatch.setattr(store.settings, "aws_secret_access_key", "SUPERSECRET123")

    def boom(**kwargs):
        raise ClientError(
            {"Error": {"Code": "SignatureDoesNotMatch", "Message": "bad sig"}},
            "GetObject",
        )

    monkeypatch.setattr(fake, "get_object", boom)

    with pytest.raises(store.StorageError) as caught:
        store.load("datasets/whatever.parquet")

    message = str(caught.value)
    assert "SUPERSECRET123" not in message
    assert store.settings.aws_endpoint_url_s3 not in message


# ---------------------------------------------------------------------------
# The boundary this module exists to enforce
# ---------------------------------------------------------------------------


def test_nothing_else_imports_boto3():
    """The bytea fallback is only "one file away" while this holds.

    Neon Object Storage is Beta. If boto3 spreads, abandoning it stops being a
    rewrite of one module and becomes a refactor of the whole app.
    """
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    offenders = []

    for path in app_dir.rglob("*.py"):
        if path.name == "dataframe_store.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "import boto3" in text or "import botocore" in text:
            offenders.append(str(path.relative_to(app_dir)))

    assert not offenders, f"these modules import boto3 directly: {offenders}"
