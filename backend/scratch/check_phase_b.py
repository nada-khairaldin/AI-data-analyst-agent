"""End-to-end check of phase B against a running server.

    # terminal 1, from backend/
    LLM_DEV_CACHE=true uvicorn app.main:app --port 8000

    # terminal 2, from backend/
    python scratch/check_phase_b.py                 # full run
    python scratch/check_phase_b.py --reuse <id>    # after restarting the
                                                    # server, to prove the
                                                    # dataset is still there

Uses the real Neon database, the real bucket and the real LLM. Turn
LLM_DEV_CACHE on: the four questions cost ~4-8 planner calls against a quota
of 20 a day.
"""

import argparse
import json
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8100"
SAMPLES = "../samples"
SESSION = str(uuid.uuid4())

QUESTIONS = [
    "Which product has the highest total quantity sold?",
    "What is the average price?",
    "Show me the best",
    "Predict next year's sales",
    # Added after the datetime rule was relaxed: min/max are allowed on a date
    # column, and the Timestamp has to come back as an ISO string.
    "What is the earliest order date?",
]


def show(label, response):
    print(f"  {label:34} {response.status_code}")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse", help="an existing dataset id, after a restart")
    parser.add_argument("--session", help="reuse a session id")
    args = parser.parse_args()

    session = args.session or SESSION
    headers = {"X-Session-Id": session}
    client = httpx.Client(base_url=BASE, headers=headers, timeout=300)

    print(f"session {session}\n")

    if args.reuse:
        print("--- after restart: is the dataset still there? ---")
        response = show("GET /api/datasets/{id}", client.get(f"/api/datasets/{args.reuse}"))
        if response.status_code != 200:
            raise SystemExit("the dataset did not survive the restart")
        body = response.json()
        print(f"      {body['name']}  {body['rowCount']} rows x {body['colCount']} cols")
        show("GET preview", client.get(f"/api/datasets/{args.reuse}/preview"))
        print("\nSURVIVED THE RESTART")
        return

    print("--- health ---")
    show("GET /health", client.get("/health"))

    print("\n--- upload orders.csv ---")
    with open(f"{SAMPLES}/orders.csv", "rb") as handle:
        response = show(
            "POST /api/datasets",
            client.post(
                "/api/datasets",
                files={"file": ("orders.csv", handle.read(), "text/csv")},
            ),
        )
    dataset = response.json()
    print(f"      id={dataset['id']}")
    print(f"      {dataset['rowCount']} rows x {dataset['colCount']} cols, "
          f"{dataset['size']}, missing {dataset['missingRate']}, "
          f"dupes {dataset['duplicateRate']}")
    dataset_id = dataset["id"]

    print("\n--- the other dataset endpoints ---")
    show("GET /api/datasets", client.get("/api/datasets"))
    report = show("GET .../report", client.get(f"/api/datasets/{dataset_id}/report"))
    body = report.json()
    print(f"      {body['checksCompleted']} checks, {body['noticeCount']} notices, "
          f"quality {body['qualityScore']} ({body['qualityLabel']})")
    columns = show("GET .../columns", client.get(f"/api/datasets/{dataset_id}/columns"))
    excluded = [c["name"] for c in columns.json()["columns"] if not c["available"]]
    print(f"      excluded: {excluded}")
    preview = show("GET .../preview", client.get(f"/api/datasets/{dataset_id}/preview"))
    print(f"      {len(preview.json()['rows'])} rows, "
          f"{len(preview.json()['columns'])} columns")
    show("GET /api/limits", client.get("/api/limits"))

    print("\n--- bad.csv must be rejected ---")
    with open(f"{SAMPLES}/bad.csv", "rb") as handle:
        response = client.post(
            "/api/datasets", files={"file": ("bad.csv", handle.read(), "text/csv")}
        )
    show("POST /api/datasets (bad.csv)", response)
    if response.status_code != 422:
        raise SystemExit(f"expected 422, got {response.status_code}")
    details = response.json()["error"]["details"]
    print(f"      code={response.json()['error']['code']}")
    for key in ("filename", "fileSize", "missingRate", "maxAllowed"):
        print(f"      {key}: {details.get(key)}")
    print(f"      reasons: {details.get('reasons')}")

    print("\n--- one conversation, four questions ---")
    conversation = show(
        "POST .../conversations",
        client.post(f"/api/datasets/{dataset_id}/conversations", json={}),
    ).json()
    conversation_id = conversation["id"]

    for question in QUESTIONS:
        print(f"\n  Q: {question}")
        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": question},
        )
        print(f"     HTTP {response.status_code}")
        if response.status_code != 201:
            print(f"     error: {json.dumps(response.json())[:200]}")
            continue
        message = response.json()["message"]
        print(f"     status   : {message['status']}")
        print(f"     answer   : {(message['content'] or '')[:150]}")
        if message.get("resultData") is not None:
            print(f"     result   : {json.dumps(message['resultData'])[:120]}")
            print(f"     kind     : {message['resultKind']}")
        if message.get("plan"):
            print(f"     steps    : {message['plan']['steps']}")
        print(f"     chart    : {message['showChart']} {message.get('chartTitle') or ''}")

    print("\n--- read the whole conversation back ---")
    history = show(
        "GET .../messages",
        client.get(f"/api/conversations/{conversation_id}/messages"),
    ).json()
    print(f"      title: {history['title']}")
    print(f"      {len(history['messages'])} messages")
    for message in history["messages"]:
        role = message["role"]
        status = message.get("status") or ""
        print(f"        {role:6} {status:20} {(message['content'] or '')[:70]}")

    print("\n" + "=" * 62)
    print(f"  dataset id: {dataset_id}")
    print(f"  session   : {session}")
    print("  Restart the server, then run:")
    print(f"    python scratch/check_phase_b.py --reuse {dataset_id} "
          f"--session {session}")
    print("=" * 62)


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("No server on 127.0.0.1:8000. Start uvicorn first.", file=sys.stderr)
        raise SystemExit(1)
