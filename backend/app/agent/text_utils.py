"""Deterministic cleanup of model output, before anything tries to parse it.

Kept out of llm.py so it can be tested exhaustively without a client, and out
of validators.py because a markdown fence is a *provider* quirk, not a
validation rule — validators.py should keep describing what a valid plan is,
not what Gemini happens to wrap it in.
"""

import re

# ```json\n{...}\n```  or  ```\n{...}\n```  — the language tag is optional and
# Gemini has used both. Anchored at both ends with DOTALL so the body may
# contain newlines and braces, and non-greedy so only the outermost fence is
# consumed.
_FENCED = re.compile(
    r"""
    \A\s*                 # leading whitespace
    ```[ \t]*             # opening fence
    (?:[A-Za-z0-9_+-]+)?  # optional language tag: json, JSON, js, ...
    [ \t]*\r?\n           # end of the opening line
    (?P<body>.*?)         # the payload
    \r?\n?[ \t]*```       # closing fence
    \s*\Z                 # trailing whitespace
    """,
    re.DOTALL | re.VERBOSE,
)

# A fence that opens but never closes. Gemini produces this when the reply is
# cut off at max_output_tokens, and the body is often still complete enough to
# parse, so it is worth salvaging rather than failing.
_FENCE_OPEN_ONLY = re.compile(
    r"\A\s*```[ \t]*(?:[A-Za-z0-9_+-]+)?[ \t]*\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)


def strip_code_fence(text):
    """Remove a surrounding markdown code fence, if there is exactly one.

    Deterministic and conservative:

    - Returns the input unchanged when there is no fence, so a plain JSON
      reply is never touched.
    - Only strips a fence that wraps the WHOLE string. Prose with a fenced
      block in the middle is left alone, because guessing which part was meant
      to be the answer is how a parser starts silently picking the wrong one.
    - Handles an unterminated opening fence, which is what a truncated reply
      looks like.

    Non-str input is returned as-is, so this is safe to apply blindly to
    whatever a provider hands back.
    """
    if not isinstance(text, str):
        return text

    match = _FENCED.match(text)
    if match:
        return match.group("body").strip()

    match = _FENCE_OPEN_ONLY.match(text)
    if match:
        body = match.group("body")
        # Drop a trailing partial fence if the truncation landed mid-marker.
        body = re.sub(r"\r?\n?[ \t]*`{1,3}[ \t]*\Z", "", body)
        return body.strip()

    return text.strip()
