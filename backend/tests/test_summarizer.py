"""Tests for the rolling fact sheet (phase C2).

The trigger arithmetic and the heading guard are the two things worth pinning:
the first controls how much the free tier is charged, and the second is what
stops prose being stored where later turns expect a filter line.
"""

import pytest

from app.services import summarizer

GOOD = """Goal: understand product sales
Definitions & agreements:
- revenue = Price x quantity
Active filters/assumptions:
- 2024 only
Key findings:
- Mouse highest quantity, 70 units (all-time)"""


class FakeConversation:
    def __init__(self, exchange_count):
        self.id = "c1"
        self.exchange_count = exchange_count


class FakeSummary:
    def __init__(self, exchange_count, summary="old sheet"):
        self.exchange_count = exchange_count
        self.summary = summary
        self.covers_through_id = None


# ---------------------------------------------------------------------------
# The heading guard
# ---------------------------------------------------------------------------


def test_all_four_headings_are_required():
    assert summarizer.is_usable(GOOD) is True


@pytest.mark.parametrize(
    "text,why",
    [
        ("", "empty"),
        ("   ", "whitespace"),
        ("The user asked about products, then months.", "narrative"),
        ("Goal: x\nDefinitions & agreements: y\nKey findings: z", "missing a heading"),
        ("Goal: x", "one heading"),
    ],
)
def test_a_reply_without_the_headings_is_rejected(text, why):
    """Rejected because the headings ARE the contract: without them the
    "Active filters" line cannot be found, and keeping the previous sheet is
    strictly better than storing something later turns will misread."""
    assert summarizer.is_usable(text) is False, why


def test_headings_are_matched_case_insensitively():
    assert summarizer.is_usable(GOOD.lower()) is True


def test_a_runaway_reply_is_trimmed():
    text = "Goal: " + " ".join(["word"] * 1000)

    assert len(summarizer.trim(text).split()) <= summarizer.MAX_WORDS * 2


def test_a_normal_sheet_is_not_trimmed():
    assert summarizer.trim(GOOD) == GOOD.strip()


# ---------------------------------------------------------------------------
# The trigger — this is the free-tier budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exchanges,covered,expected",
    [
        (1, 0, False),
        (3, 0, False),  # the window still holds everything
        (4, 0, False),  # only one exchange has left it
        (5, 0, True),  # two have: 5 - 3 - 0 = 2
        (6, 0, True),
        (6, 2, False),  # 6 - 3 - 2 = 1, not yet
        (7, 2, True),  # 7 - 3 - 2 = 2
        (8, 2, True),
    ],
)
def test_the_refresh_trigger(monkeypatch, exchanges, covered, expected):
    """exchanges - window - already_summarised >= 2, which amortises the
    summariser to ~0.5 calls per turn."""
    monkeypatch.setattr(
        summarizer.settings, "history_window_exchanges", 3, raising=False
    )
    monkeypatch.setattr(
        summarizer.settings, "summary_refresh_exchanges", 2, raising=False
    )

    assert summarizer.is_due(FakeConversation(exchanges), FakeSummary(covered)) is expected


def test_the_first_refresh_needs_no_existing_summary(monkeypatch):
    monkeypatch.setattr(
        summarizer.settings, "history_window_exchanges", 3, raising=False
    )
    monkeypatch.setattr(
        summarizer.settings, "summary_refresh_exchanges", 2, raising=False
    )

    assert summarizer.is_due(FakeConversation(5), None) is True
    assert summarizer.is_due(FakeConversation(4), None) is False


def test_a_wider_window_delays_the_first_refresh(monkeypatch):
    monkeypatch.setattr(
        summarizer.settings, "history_window_exchanges", 5, raising=False
    )
    monkeypatch.setattr(
        summarizer.settings, "summary_refresh_exchanges", 2, raising=False
    )

    assert summarizer.is_due(FakeConversation(6), None) is False
    assert summarizer.is_due(FakeConversation(7), None) is True


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------


def test_the_prompt_carries_the_existing_sheet_and_the_new_exchanges():
    prompt = summarizer.build_prompt(GOOD, "user: and per month?\n  agent: ...")

    assert "revenue = Price x quantity" in prompt
    assert "and per month?" in prompt


def test_an_empty_sheet_is_labelled_not_blank():
    prompt = summarizer.build_prompt("", "user: x")

    assert "(empty)" in prompt
    assert "{existing_summary}" not in prompt


def test_the_prompt_insists_on_keeping_agreements():
    """The one rule the whole design depends on: a filter must survive a
    refresh or "only 2024" is forgotten the moment it leaves the window."""
    prompt = summarizer.build_prompt("", "")

    assert "unless a new exchange explicitly changes or cancels it" in prompt
    assert "Never invent a number" in prompt
