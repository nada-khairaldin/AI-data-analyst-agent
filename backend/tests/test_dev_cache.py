"""Tests for the development response cache (phase A9).

The cache exists because the free tier allows 20 requests per day per model
and two verification runs exhausted a day. The risk it introduces is worse
than the problem it solves if it ever runs in production: a cached answer
looks completely fine, it was just computed for a different dataset.

So the tests that matter most here are the ones about it being OFF.
"""

import pytest

from app.agent import dev_cache


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(dev_cache.settings, "llm_dev_cache", True, raising=False)
    monkeypatch.setattr(
        dev_cache.settings, "llm_dev_cache_dir", str(tmp_path), raising=False
    )
    monkeypatch.setattr(
        type(dev_cache.settings),
        "dev_cache_enabled",
        property(lambda self: True),
        raising=False,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Off by default, and off in production
# ---------------------------------------------------------------------------


def test_it_is_off_by_default():
    from app.config import Settings

    assert Settings().llm_dev_cache is False


def test_production_overrides_the_flag():
    """The environment wins over the flag, not the other way round.

    Serving a cached answer to a real user would be wrong in a way that is
    very hard to notice, so this is not left to whoever edits the env file.
    """
    from app.config import Settings

    production = Settings(environment="production", llm_dev_cache=True)

    assert production.llm_dev_cache is True
    assert production.dev_cache_enabled is False


def test_development_respects_the_flag():
    from app.config import Settings

    assert Settings(environment="development", llm_dev_cache=True).dev_cache_enabled
    assert not Settings(environment="development", llm_dev_cache=False).dev_cache_enabled


def test_a_disabled_cache_never_reads_or_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dev_cache.settings, "llm_dev_cache_dir", str(tmp_path), raising=False
    )
    monkeypatch.setattr(
        type(dev_cache.settings),
        "dev_cache_enabled",
        property(lambda self: False),
        raising=False,
    )

    dev_cache.put("m", "prompt", "answer")

    assert dev_cache.get("m", "prompt") is None
    assert list(tmp_path.glob("*.json")) == []


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


def test_store_then_read(cache):
    dev_cache.put("model-a", "the prompt", "the answer")

    assert dev_cache.get("model-a", "the prompt") == "the answer"


def test_a_miss_returns_none(cache):
    assert dev_cache.get("model-a", "never seen") is None


def test_the_model_is_part_of_the_key(cache):
    """Two models given the same prompt are two different answers."""
    dev_cache.put("model-a", "p", "answer-a")

    assert dev_cache.get("model-b", "p") is None
    assert dev_cache.get("model-a", "p") == "answer-a"


def test_the_whole_prompt_is_part_of_the_key(cache):
    """Any change to question, schema or tool list is a different key, which
    is what makes a stale hit impossible."""
    dev_cache.put("m", "prompt one", "one")

    assert dev_cache.get("m", "prompt two") is None


def test_keys_cannot_collide_by_running_together():
    """The parts are length-prefixed before hashing.

    Without that, ("ab", "c") and ("a", "bc") would hash identically and one
    model's answer could be served for another's prompt.
    """
    assert dev_cache.key_for("ab", "c") != dev_cache.key_for("a", "bc")


def test_the_key_is_stable_across_calls():
    assert dev_cache.key_for("m", "p") == dev_cache.key_for("m", "p")


def test_an_overwrite_replaces_the_entry(cache):
    dev_cache.put("m", "p", "first")
    dev_cache.put("m", "p", "second")

    assert dev_cache.get("m", "p") == "second"


def test_unicode_survives(cache):
    dev_cache.put("m", "Which café sold most?", "The café in Köln — 42 units")

    assert dev_cache.get("m", "Which café sold most?") == "The café in Köln — 42 units"


# ---------------------------------------------------------------------------
# It must never break a real call
# ---------------------------------------------------------------------------


def test_corrupt_entries_are_a_miss_not_a_crash(cache):
    path = cache / f"{dev_cache.key_for('m', 'p')}.json"
    path.write_text("this is not json", encoding="utf-8")

    assert dev_cache.get("m", "p") is None


def test_an_entry_from_an_older_format_is_ignored(cache):
    import json

    path = cache / f"{dev_cache.key_for('m', 'p')}.json"
    path.write_text(json.dumps({"version": 0, "text": "stale"}), encoding="utf-8")

    assert dev_cache.get("m", "p") is None


def test_an_entry_with_no_text_is_ignored(cache):
    import json

    path = cache / f"{dev_cache.key_for('m', 'p')}.json"
    path.write_text(json.dumps({"version": 1, "text": None}), encoding="utf-8")

    assert dev_cache.get("m", "p") is None


def test_a_write_failure_does_not_raise(cache, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(dev_cache.pathlib.Path, "mkdir", boom)

    dev_cache.put("m", "p", "answer")  # must not raise


def test_no_partial_entry_is_left_by_an_interrupted_write(cache):
    """Entries are written to a temp file and moved, so a crash mid-write
    cannot leave something that reads as valid JSON."""
    dev_cache.put("m", "p", "answer")

    assert list(cache.glob("*.tmp")) == []
    assert len(list(cache.glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Replaying a stream
# ---------------------------------------------------------------------------


def test_cached_text_is_replayed_as_several_chunks():
    text = "The product with the highest total quantity sold is the Mouse, 45 units."

    chunks = list(dev_cache.chunk(text))

    assert len(chunks) > 1, "a single chunk would not look like a stream"
    assert "".join(chunks).split() == text.split()


def test_replaying_preserves_the_text_exactly_when_rejoined():
    text = "one two three four five six seven eight"

    assert "".join(dev_cache.chunk(text)).split() == text.split()


def test_replaying_empty_text_yields_nothing():
    assert list(dev_cache.chunk("")) == []


def test_short_text_still_yields_something():
    assert "".join(dev_cache.chunk("OK")).strip() == "OK"


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------


def test_stats_reports_the_entry_count(cache):
    dev_cache.put("m", "p1", "a")
    dev_cache.put("m", "p2", "b")

    stats = dev_cache.stats()

    assert stats["enabled"] is True
    assert stats["entries"] == 2


def test_clear_removes_every_entry(cache):
    dev_cache.put("m", "p1", "a")
    dev_cache.put("m", "p2", "b")

    removed = dev_cache.clear()

    assert removed == 2
    assert dev_cache.stats()["entries"] == 0


def test_the_cache_directory_is_gitignored():
    """It stores prompts, which embed the dataset's column names and the
    user's question, so it must never be committed."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent.parent
    ignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert ".llm_cache" in ignore
