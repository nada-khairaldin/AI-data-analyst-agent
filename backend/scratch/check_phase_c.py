"""Live check of phase C: memory across four turns, on one conversation.

    # terminal 1, from backend/
    LLM_DEV_CACHE=true uvicorn app.main:app --port 8100

    # terminal 2, from backend/
    python scratch/check_phase_c.py

Turn 3 is an instruction, so it must cost 1 LLM call and run no planner.
Turn 4 must apply the 2024 agreement it was given in turn 3.
"""

import json
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8100"
SAMPLES = "../samples"

TURNS = [
    "Which product has the highest total quantity sold?",
    "Now show it per month",
    "Only 2024 from now on",
    "What is the total revenue per country?",
]


def main():
    session = str(uuid.uuid4())
    headers = {"X-Session-Id": session}
    client = httpx.Client(base_url=BASE, headers=headers, timeout=600)

    with open(f"{SAMPLES}/orders.csv", "rb") as handle:
        dataset = client.post(
            "/api/datasets",
            files={"file": ("orders.csv", handle.read(), "text/csv")},
        ).json()
    print(f"dataset {dataset['id']}  session {session}\n")

    conversation = client.post(
        f"/api/datasets/{dataset['id']}/conversations", json={}
    ).json()
    conversation_id = conversation["id"]

    results = []
    for index, question in enumerate(TURNS, 1):
        print("=" * 70)
        print(f"TURN {index}: {question}")
        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": question},
        )
        if response.status_code != 201:
            print(f"  HTTP {response.status_code}: {response.text[:300]}")
            results.append((question, "ERROR", None, response.status_code, ""))
            continue

        message = response.json()["message"]
        kind = "instruction" if message["plan"] is None and message["resultData"] is None else "question"
        print(f"  kind              : {kind}")
        print(f"  condensedQuestion : {message['condensedQuestion']}")
        print(f"  status            : {message['status']}")
        print(f"  answer            : {(message['content'] or '')[:160]}")
        if message["resultData"] is not None:
            print(f"  result            : {json.dumps(message['resultData'])[:160]}")
        if message["plan"]:
            print(f"  steps             : {message['plan']['steps']}")
            print(f"  filters           : {message['plan']['filters']}")
        results.append(
            (question, kind, message["condensedQuestion"], message["status"], message["content"])
        )

    print("\n" + "=" * 70)
    print("history as stored")
    history = client.get(f"/api/conversations/{conversation_id}/messages").json()
    print(f"  title: {history['title']}  ({len(history['messages'])} messages)")
    for message in history["messages"]:
        print(f"    {message['role']:6} {(message.get('status') or ''):20} "
              f"{(message['content'] or '')[:60]}")

    print("\n" + "=" * 70)
    print(f"  dataset    : {dataset['id']}")
    print(f"  session    : {session}")
    print(f"  conversation: {conversation_id}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("No server on 127.0.0.1:8100.", file=sys.stderr)
        raise SystemExit(1)
