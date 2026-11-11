"""Tests for app/agent/llm.py (phases A8 and A9).

No network: every model is a stub. The live checks belong to
scratch/check_model.py.

The behaviour under test exists because of one measured number — the Gemini
free tier allows 20 generateContent requests per day, per model. So what
matters here is the arithmetic of calls: that a 429 moves to the next model
rather than sleeping, that a non-429 does not burn the whole chain, and that
one question costs one planner call rather than two.
"""

import pytest

from app.agent import llm


class FakeReply:
    """Stands in for an AIMessage.

    ``content`` is a LIST of blocks, as langchain-core 1.x returns, and
    ``text`` flattens it. Shaped this way deliberately: code that reached for
    ``.content`` would pass a naive stub and fail against the real provider
    with "expected str instance, list found".
    """

    def __init__(self, text="OK"):
        self._text = text
        self.content = [{"type": "text", "text": text, "extras": {}}]
        self.usage_metadata = {"input_tokens": 1, "output_tokens": 1}

    @property
    def text(self):
        return self._text


class FakeClient:
    def __init__(self, name, reply="OK", error=None, fail_times=0):
        self.name = name
        self.reply = reply
        self.error = error
        self.fail_times = fail_times
        self.calls = 0

    def _maybe_raise(self):
        self.calls += 1
        if self.error and self.calls <= self.fail_times:
            raise self.error

    def invoke(self, prompt):
        self._maybe_raise()
        return FakeReply(self.reply)

    def stream(self, prompt):
        self._maybe_raise()
        for piece in ("1 ", "2 ", "3"):
            yield FakeReply(piece)


class ResourceExhausted(Exception):
    """Mimics google-api-core's 429 by class name, as the real one arrives."""


ALWAYS = 10_000


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Clean client cache, no sleeping, and no cache leaking between tests."""
    llm.reset_models()
    monkeypatch.setattr(llm.settings, "llm_dev_cache", False, raising=False)
    monkeypatch.setattr(
        llm.settings, "llm_dev_cache_dir", str(tmp_path / "cache"), raising=False
    )
    yield
    llm.reset_models()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    return slept


@pytest.fixture
def clients(monkeypatch):
    """Install a per-model fake client registry."""
    registry = {}

    def install(**per_model):
        registry.update(per_model)

        def fake_get_model(model, *, role=llm.FAST):
            if model not in registry:
                registry[model] = FakeClient(model)
            return registry[model]

        monkeypatch.setattr(llm, "get_model", fake_get_model)
        return registry

    return install


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------


def test_each_role_has_its_own_chain():
    assert llm.chain_for(llm.PLANNER) == llm.settings.planner_models
    assert llm.chain_for(llm.FAST) == llm.settings.fast_models


def test_chains_are_not_empty_and_do_not_overlap_at_the_head():
    """The two roles exist to use different models; if the heads matched, the
    cheap model would be planning or vice versa."""
    planner = llm.chain_for(llm.PLANNER)
    fast = llm.chain_for(llm.FAST)

    assert planner and fast
    assert planner[0] != fast[0]


def test_model_name_is_the_head_of_the_chain():
    assert llm.model_name(llm.PLANNER) == llm.chain_for(llm.PLANNER)[0]


def test_an_unknown_role_is_rejected():
    with pytest.raises(ValueError, match="Unknown model role"):
        llm.chain_for("supervisor")


def test_an_empty_chain_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_planner_models", "", raising=False)
    monkeypatch.setattr(
        type(llm.settings), "planner_models", property(lambda self: []), raising=False
    )

    with pytest.raises(llm.LLMNotConfigured, match="LLM_PLANNER_MODELS"):
        llm.chain_for(llm.PLANNER)


def test_a_chain_drops_duplicates():
    """The same model twice would burn a second call on a refused quota."""
    from app.config import _split_models

    assert _split_models("a, b , a,,b , c") == ["a", "b", "c"]


def test_a_chain_preserves_preference_order():
    from app.config import _split_models

    assert _split_models("first,second,third") == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# Failover: the point of the whole exercise
# ---------------------------------------------------------------------------


def test_the_first_model_answers_when_it_can(clients):
    chain = llm.chain_for(llm.PLANNER)
    registry = clients(**{chain[0]: FakeClient(chain[0], reply="from-first")})

    assert llm.complete("hi", role=llm.PLANNER) == "from-first"
    assert registry[chain[0]].calls == 1


def test_a_429_falls_through_to_the_next_model_immediately(clients, no_sleep):
    """The quota is per model, so another model may well answer — and a DAILY
    limit will not clear by waiting, which is why there is no sleep here."""
    chain = llm.chain_for(llm.PLANNER)
    registry = clients(
        **{
            chain[0]: FakeClient(
                chain[0], error=ResourceExhausted("429 quota"), fail_times=ALWAYS
            ),
            chain[1]: FakeClient(chain[1], reply="from-fallback"),
        }
    )

    result = llm.complete("hi", role=llm.PLANNER)

    assert result == "from-fallback"
    assert registry[chain[1]].calls == 1
    assert no_sleep == [], "falling through to another model must not sleep"


def test_it_walks_the_whole_fast_chain(clients):
    chain = llm.chain_for(llm.FAST)
    assert len(chain) >= 3, "this test needs a chain of at least three"

    registry = clients(
        **{
            chain[0]: FakeClient(chain[0], error=ResourceExhausted("429"), fail_times=ALWAYS),
            chain[1]: FakeClient(chain[1], error=ResourceExhausted("429"), fail_times=ALWAYS),
            chain[2]: FakeClient(chain[2], reply="third"),
        }
    )

    assert llm.complete("hi", role=llm.FAST) == "third"
    assert registry[chain[2]].calls == 1


def test_the_readable_429_is_raised_only_when_every_model_is_exhausted(
    clients, monkeypatch
):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 0, raising=False)
    chain = llm.chain_for(llm.FAST)
    registry = clients(
        **{
            name: FakeClient(name, error=ResourceExhausted("429"), fail_times=ALWAYS)
            for name in chain
        }
    )

    with pytest.raises(llm.LLMRateLimited) as caught:
        llm.complete("hi", role=llm.FAST)

    assert all(registry[name].calls == 1 for name in chain), "every model is tried"
    message = str(caught.value)
    assert "every available model" in message
    assert "429" not in message, "an HTTP code is not an explanation"


def test_after_the_chain_is_exhausted_it_backs_off_and_retries_the_chain(
    clients, monkeypatch, no_sleep
):
    """A per-minute limit does recover, so one wait-and-retry is worthwhile
    once failover has been tried."""
    monkeypatch.setattr(llm.settings, "llm_max_retries", 1, raising=False)
    chain = llm.chain_for(llm.FAST)
    clients(
        **{
            name: FakeClient(name, error=ResourceExhausted("429"), fail_times=ALWAYS)
            for name in chain
        }
    )

    with pytest.raises(llm.LLMRateLimited):
        llm.complete("hi", role=llm.FAST)

    assert len(no_sleep) == 1, "one backoff between the two rounds"


def test_a_non_rate_limit_error_does_not_burn_the_chain(clients, no_sleep):
    """A malformed request fails identically on every model, so trying them
    all would spend three days' quota on one bad prompt."""
    chain = llm.chain_for(llm.PLANNER)
    registry = clients(
        **{
            chain[0]: FakeClient(
                chain[0], error=Exception("400 invalid argument"), fail_times=ALWAYS
            ),
            chain[1]: FakeClient(chain[1], reply="should-not-be-reached"),
        }
    )

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi", role=llm.PLANNER)

    assert registry[chain[1]].calls == 0, "the second model must not be tried"
    assert not isinstance(caught.value, llm.LLMRateLimited)
    assert no_sleep == []


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
    assert llm._is_rate_limit(error) is True


def test_an_ordinary_error_is_not_mistaken_for_a_429():
    assert llm._is_rate_limit(Exception("invalid argument: bad schema")) is False


def test_a_nine_hour_retry_after_is_ignored():
    """Against a DAILY quota Gemini returns retryDelay=34705s. Sleeping that
    long is not something a request can do, so the cap turns it into a 429."""

    class DailyQuota(Exception):
        retry_after = 34705

    assert llm._retry_after(DailyQuota()) is None


def test_a_short_retry_after_is_honoured():
    class PerMinute(Exception):
        retry_after = 7

    assert llm._retry_after(PerMinute()) == 7.0


# ---------------------------------------------------------------------------
# Thinking capability follows the MODEL, not the role
# ---------------------------------------------------------------------------


def test_a_model_that_rejects_the_budget_is_retried_without_it(clients, monkeypatch):
    """models.list reports thinking=True for every model in both chains, yet
    gemini-3.5-flash-lite accepts 512 or -1 and REJECTS 0. The capability is
    not discoverable, so it is learned."""
    monkeypatch.setattr(llm.settings, "llm_thinking_budget", 0, raising=False)
    chain = llm.chain_for(llm.PLANNER)
    registry = clients(
        **{
            chain[0]: FakeClient(
                chain[0],
                error=Exception("400 INVALID_ARGUMENT"),
                fail_times=1,
            )
        }
    )

    result = llm.complete("hi", role=llm.PLANNER)

    assert result == "OK"
    assert registry[chain[0]].calls == 2, "one rejection, one retry"
    assert chain[0] in llm._rejects_thinking_budget


def test_the_rejection_is_remembered_so_it_happens_once(clients, monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_thinking_budget", 0, raising=False)
    chain = llm.chain_for(llm.PLANNER)
    clients(
        **{
            chain[0]: FakeClient(
                chain[0], error=Exception("400 INVALID_ARGUMENT"), fail_times=1
            )
        }
    )

    llm.complete("hi", role=llm.PLANNER)
    assert llm._thinking_kwargs(chain[0]) == {}


def test_no_budget_is_sent_when_none_is_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_thinking_budget", None, raising=False)

    assert llm._thinking_kwargs("any-model") == {}


def test_the_budget_is_sent_when_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_thinking_budget", 0, raising=False)

    assert llm._thinking_kwargs("some-model") == {"thinking_budget": 0}


def test_thinking_is_not_decided_by_role(monkeypatch):
    """The regression this replaces: the budget used to be applied to the
    PLANNER role, so pointing the planner at a -lite model failed every call
    with a bare INVALID_ARGUMENT."""
    monkeypatch.setattr(llm.settings, "llm_thinking_budget", 7, raising=False)

    assert llm._thinking_kwargs("m") == {"thinking_budget": 7}
    llm._rejects_thinking_budget.add("m")
    assert llm._thinking_kwargs("m") == {}


# ---------------------------------------------------------------------------
# JSON mode and fences
# ---------------------------------------------------------------------------


def test_json_mode_is_requested_for_the_planner_only(monkeypatch):
    llm.reset_models()
    captured = {}

    class Recorder:
        def __init__(self, **kwargs):
            captured[(kwargs["model"], kwargs.get("response_mime_type"))] = kwargs

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "x", raising=False)
    monkeypatch.setattr(llm.settings, "llm_planner_json_mode", True, raising=False)

    llm.get_model("m1", role=llm.PLANNER)
    llm.get_model("m2", role=llm.FAST)

    assert ("m1", "application/json") in captured
    assert ("m2", None) in captured


def test_a_fenced_reply_is_still_parsed(clients):
    """JSON mode is a request, not a guarantee; the fence strip is the belt."""
    chain = llm.chain_for(llm.PLANNER)
    clients(**{chain[0]: FakeClient(chain[0], reply='```json\n{"status": "ready"}\n```')})

    assert llm.complete("hi", role=llm.PLANNER) == '{"status": "ready"}'


def test_an_unfenced_reply_is_untouched(clients):
    chain = llm.chain_for(llm.PLANNER)
    clients(**{chain[0]: FakeClient(chain[0], reply='{"status": "ready"}')})

    assert llm.complete("hi", role=llm.PLANNER) == '{"status": "ready"}'


def test_complete_returns_a_plain_string(clients):
    chain = llm.chain_for(llm.PLANNER)
    clients(**{chain[0]: FakeClient(chain[0], reply="the answer")})

    result = llm.complete("hi", role=llm.PLANNER)

    assert result == "the answer"
    assert isinstance(result, str)


def test_stream_yields_strings(clients):
    chain = llm.chain_for(llm.FAST)
    clients(**{chain[0]: FakeClient(chain[0])})

    pieces = list(llm.stream("hi", role=llm.FAST))

    assert pieces == ["1 ", "2 ", "3"]
    assert all(isinstance(p, str) for p in pieces)


# ---------------------------------------------------------------------------
# Safety of messages
# ---------------------------------------------------------------------------


def test_provider_internals_do_not_reach_the_user(clients, monkeypatch):
    chain = llm.chain_for(llm.PLANNER)
    clients(
        **{
            name: FakeClient(
                name,
                error=Exception("500 at projects/abc/locations/us/models/internal-x"),
                fail_times=ALWAYS,
            )
            for name in chain
        }
    )

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi", role=llm.PLANNER)

    assert "projects/abc" not in str(caught.value)


def test_the_api_key_never_appears_in_an_error(clients, monkeypatch):
    monkeypatch.setattr(llm.settings, "gemini_api_key", "SECRET-KEY-123", raising=False)
    chain = llm.chain_for(llm.PLANNER)
    clients(
        **{
            name: FakeClient(
                name,
                error=Exception("auth failed for key SECRET-KEY-123"),
                fail_times=ALWAYS,
            )
            for name in chain
        }
    )

    with pytest.raises(llm.LLMError) as caught:
        llm.complete("hi", role=llm.PLANNER)

    assert "SECRET-KEY-123" not in str(caught.value)


def test_status_codes():
    assert llm.LLMRateLimited.status_code == 429
    assert llm.LLMRateLimited.code == "LLM_RATE_LIMITED"
    assert llm.LLMNotConfigured.status_code == 503
    assert llm.LLMError.status_code == 502


def test_a_missing_key_is_its_own_error(monkeypatch):
    llm.reset_models()
    monkeypatch.setattr(llm.settings, "gemini_api_key", "", raising=False)

    with pytest.raises(llm.LLMNotConfigured) as caught:
        llm.get_model("m", role=llm.FAST)

    assert "GEMINI_API_KEY" in str(caught.value)


def test_the_api_key_is_passed_explicitly(monkeypatch):
    """Not left to the SDK's GOOGLE_API_KEY / GEMINI_API_KEY lookup, which
    fails when only the latter is set and ADC is also present."""
    llm.reset_models()
    captured = {}

    class Recorder:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "a-key", raising=False)

    llm.get_model("m", role=llm.FAST)

    assert captured["google_api_key"] == "a-key"


def test_clients_are_built_once_per_configuration(monkeypatch):
    llm.reset_models()
    built = []

    class Recorder:
        def __init__(self, **kwargs):
            built.append(kwargs["model"])

    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", Recorder)
    monkeypatch.setattr(llm.settings, "gemini_api_key", "x", raising=False)

    llm.get_model("m1", role=llm.FAST)
    llm.get_model("m1", role=llm.FAST)
    llm.get_model("m2", role=llm.FAST)

    assert built == ["m1", "m2"]


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------


def test_only_llm_py_talks_to_a_provider():
    """Switching provider stays a one-file job only while this holds."""
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    markers = ("langchain_google_genai", "google.genai", "import openai", "from openai")
    offenders = []

    for path in app_dir.rglob("*.py"):
        if path.name == "llm.py":
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in markers):
            offenders.append(str(path.relative_to(app_dir)))

    assert not offenders, f"these modules reach a provider directly: {offenders}"


def test_core_uses_the_planner_and_explainer_uses_the_fast_model():
    import pathlib

    agent = pathlib.Path(__file__).resolve().parent.parent / "app" / "agent"

    assert "role=PLANNER" in (agent / "core.py").read_text(encoding="utf-8")
    assert "role=FAST" in (agent / "explainer.py").read_text(encoding="utf-8")
