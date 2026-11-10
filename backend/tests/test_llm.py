"""Tests for app/agent/llm.py (phase A8).

No network: every model is a stub. The live checks belong to
scratch/check_model.py, which talks to the real API and reports latency,
token usage and whether streaming is incremental.

What these cover is the logic that is easy to get wrong and invisible when it
is: reading a reply out of the content-blocks format, retrying a 429 and only
a 429, and keeping the API key out of anything a user or a log can see.
"""

import pytest

from app.agent import llm


class FakeReply:
    """Stands in for an AIMessage.

    ``content`` is a LIST of blocks, as langchain-core 1.x returns, and
    ``text`` is the accessor that flattens it. Shaped this way deliberately:
    code that reaches for ``.content`` would pass a naive stub and fail
    against the real provider with "expected str instance, list found".
    """

    def __init__(self, text="OK"):
        self._text = text
        self.content = [{"type": "text", "text": text, "extras": {}}]
        self.usage_metadata = {"input_tokens": 1, "output_tokens": 1}

    @property
    def text(self):
        return self._text


class FakeModel:
    def __init__(self, reply="OK", raises=None, fail_times=0):
        self.reply = reply
        self.raises = raises
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        if self.raises and self.calls <= self.fail_times:
            raise self.raises
        if self.raises and self.fail_times == 0:
            raise self.raises
        return FakeReply(self.reply)

    def stream(self, prompt):
        self.calls += 1
        if self.raises and self.calls <= self.fail_times:
            raise self.raises
        if self.raises and self.fail_times == 0:
            raise self.raises
        for piece in ("1 ", "2 ", "3"):
            yield FakeReply(piece)


class ResourceExhausted(Exception):
    """Mimics google-api-core's 429 by class name, as the real one arrives."""


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Backoff is asserted by call count, not by making the suite wait."""
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    return slept


@pytest.fixture
def stub(monkeypatch):
    def install(model, role=None):
        monkeypatch.setattr(llm, "get_model", lambda r=llm.PLANNER: model)
        return model

    return install


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_the_two_roles_use_different_models():
    """The whole point of two roles: the planner gets the stronger model and
    the frequent cheap work does not."""
    assert llm.model_name(llm.PLANNER) == llm.settings.llm_planner_model
    assert llm.model_name(llm.FAST) == llm.settings.llm_fast_model


def test_an_unknown_role_is_rejected():
    llm.reset_models()
    with pytest.raises(ValueError, match="Unknown model role"):
        llm.get_model("supervisor")


def test_models_are_built_once_per_role(monkeypatch):
    """Rebuilding a client per call would discard its connection pool."""
    llm.reset_models()
    built = []

    class Recorder:
        def __init__(self, **kwargs):
            built.append(kwargs["model"])

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "x", raising=False)

    llm.get_model(llm.PLANNER)
    llm.get_model(llm.PLANNER)
    llm.get_model(llm.FAST)

    assert len(built) == 2, "each role should be constructed exactly once"
    llm.reset_models()


def test_the_planner_gets_a_thinking_budget_and_the_fast_model_does_not(monkeypatch):
    """gemini-3.8-flash is a reasoning model; the lite model is not and warns
    that it ignores sampling parameters."""
    llm.reset_models()
    captured = {}

    class Recorder:
        def __init__(self, **kwargs):
            captured[kwargs["model"]] = kwargs

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "x", raising=False)
    monkeypatch.setattr(llm.settings, "llm_planner_thinking_budget", 0, raising=False)

    llm.get_model(llm.PLANNER)
    llm.get_model(llm.FAST)

    planner = captured[llm.settings.llm_planner_model]
    fast = captured[llm.settings.llm_fast_model]
    assert planner["thinking_budget"] == 0
    assert "thinking_budget" not in fast
    llm.reset_models()


def test_the_api_key_is_passed_explicitly(monkeypatch):
    """Not left to the SDK's GOOGLE_API_KEY / GEMINI_API_KEY lookup, which
    fails outright when only the latter is set and ADC is also present."""
    llm.reset_models()
    captured = {}

    class Recorder:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "a-key", raising=False)

    llm.get_model(llm.FAST)

    assert captured["google_api_key"] == "a-key"
    llm.reset_models()


def test_a_missing_key_is_its_own_error(monkeypatch):
    llm.reset_models()
    monkeypatch.setattr(llm.settings, "gemini_api_key", "", raising=False)

    with pytest.raises(llm.LLMNotConfigured) as caught:
        llm.get_model(llm.FAST)

    assert "GEMINI_API_KEY" in str(caught.value)
    llm.reset_models()


# ---------------------------------------------------------------------------
# Reading the reply
# ---------------------------------------------------------------------------


def test_complete_returns_a_plain_string(stub):
    """Guards the content-blocks trap.

    Under langchain-core 1.x a reply is a list of block dicts. Anything
    downstream — json.loads in validators.py above all — needs a str.
    """
    stub(FakeModel(reply="the answer"))

    result = llm.complete("hi")

    assert result == "the answer"
    assert isinstance(result, str)


def test_stream_yields_strings(stub):
    stub(FakeModel())

    pieces = list(llm.stream("hi"))

    assert pieces == ["1 ", "2 ", "3"]
    assert all(isinstance(p, str) for p in pieces)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ResourceExhausted("429 quota exceeded"),
        Exception("429 Too Many Requests"),
        Exception("RESOURCE_EXHAUSTED: quota"),
        Exception("Rate limit reached for this model"),
    ],
)
def test_a_429_is_recognised_in_its_several_shapes(error):
    """google-api-core, the REST transport and LangChain each word it
    differently; the only thing they share is the text."""
    assert llm._is_rate_limit(error) is True


def test_an_ordinary_error_is_not_mistaken_for_a_429():
    assert llm._is_rate_limit(Exception("invalid argument: bad schema")) is False


def test_a_429_is_retried_and_can_succeed(stub, monkeypatch, no_sleep):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 2, raising=False)
    model = stub(FakeModel(raises=ResourceExhausted("429"), fail_times=1))

    result = llm.complete("hi")

    assert result == "OK"
    assert model.calls == 2
    assert len(no_sleep) == 1, "it should have backed off once"


def test_backoff_grows_between_attempts(stub, monkeypatch, no_sleep):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 3, raising=False)
    stub(FakeModel(raises=ResourceExhausted("429"), fail_times=99))

    with pytest.raises(llm.LLMRateLimited):
        llm.complete("hi")

    assert len(no_sleep) == 3
    assert no_sleep[1] > no_sleep[0], "the delay should increase"


def test_retries_are_bounded_and_then_it_gives_up(stub, monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 2, raising=False)
    model = stub(FakeModel(raises=ResourceExhausted("429"), fail_times=99))

    with pytest.raises(llm.LLMRateLimited):
        llm.complete("hi")

    assert model.calls == 3, "max_retries=2 means three attempts in total"


def test_the_rate_limit_message_is_readable(stub, monkeypatch):
    """It reaches the user, so it has to say what to do and nothing else."""
    monkeypatch.setattr(llm.settings, "llm_max_retries", 0, raising=False)
    stub(FakeModel(raises=ResourceExhausted("429 quota"), fail_times=99))

    with pytest.raises(llm.LLMRateLimited) as caught:
        llm.complete("hi")

    message = str(caught.value)
    assert "rate limit" in message.lower()
    assert "429" not in message, "an HTTP code is not an explanation"
    assert "Traceback" not in message


def test_a_rate_limit_maps_to_http_429():
    assert llm.LLMRateLimited.status_code == 429
    assert llm.LLMRateLimited.code == "LLM_RATE_LIMITED"


def test_a_missing_key_maps_to_503_not_429():
    assert llm.LLMNotConfigured.status_code == 503


def test_a_generic_failure_maps_to_502_not_500():
    """A provider failure is an upstream failure, not a bug in this app."""
    assert llm.LLMError.status_code == 502


# ---------------------------------------------------------------------------
# Everything else is not retried
# ---------------------------------------------------------------------------


def test_a_non_rate_limit_error_is_not_retried(stub, monkeypatch, no_sleep):
    """A malformed request fails identically the second time; retrying only
    makes the user wait longer for the same failure."""
    monkeypatch.setattr(llm.settings, "llm_max_retries", 3, raising=False)
    model = stub(FakeModel(raises=Exception("400 invalid argument"), fail_times=99))

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi")

    assert model.calls == 1
    assert no_sleep == []
    assert not isinstance(caught.value, llm.LLMRateLimited)


def test_provider_internals_do_not_reach_the_user(stub, monkeypatch):
    """The provider's own message can be long and full of internals, so it is
    logged and a short sentence is returned instead."""
    monkeypatch.setattr(llm.settings, "llm_max_retries", 0, raising=False)
    stub(
        FakeModel(
            raises=Exception("500 at projects/abc/locations/us/models/internal-x"),
            fail_times=99,
        )
    )

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi")

    assert "projects/abc" not in str(caught.value)


def test_the_api_key_never_appears_in_an_error(stub, monkeypatch):
    """The one place a key could plausibly escape into a response body."""
    monkeypatch.setattr(llm.settings, "gemini_api_key", "SECRET-KEY-123", raising=False)
    monkeypatch.setattr(llm.settings, "llm_max_retries", 0, raising=False)
    stub(FakeModel(raises=Exception("auth failed for key SECRET-KEY-123"), fail_times=99))

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi")

    assert "SECRET-KEY-123" not in str(caught.value)


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------


def test_only_llm_py_talks_to_a_provider():
    """Switching provider stays a one-file job only while this holds.

    It has already been worth it once: replacing the Hugging Face client with
    Gemini touched this module and two one-line call sites.
    """
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    markers = (
        "langchain_google_genai",
        "google.genai",
        "import openai",
        "from openai",
    )
    offenders = []

    for path in app_dir.rglob("*.py"):
        if path.name == "llm.py":
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in markers):
            offenders.append(str(path.relative_to(app_dir)))

    assert not offenders, f"these modules reach a provider directly: {offenders}"


def test_core_uses_the_planner_and_explainer_uses_the_fast_model():
    """Asserted on the source because the alternative is a live call."""
    import pathlib

    agent = pathlib.Path(__file__).resolve().parent.parent / "app" / "agent"

    core = (agent / "core.py").read_text(encoding="utf-8")
    explainer = (agent / "explainer.py").read_text(encoding="utf-8")

    assert "role=PLANNER" in core
    assert "role=FAST" in explainer
