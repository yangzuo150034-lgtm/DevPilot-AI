"""Reproducible smoke evaluation; missing tests/model costs remain null, never fabricated."""

import argparse
import json
import tempfile
import time
from pathlib import Path

from app.core.config import Settings
from app.schemas import TaskRequest
from app.service import Service

QUERIES = [
    ("def add sum return", "calculator.py", "def add"),
    ("division by zero ValueError", "calculator.py", "raise ValueError"),
    ("class CalculatorTests test_add", "tests/test_calculator.py", "def test_add"),
    ("test_divide assertRaises", "tests/test_calculator.py", "def test_divide"),
    ("add sum calculator", "calculator.py", "return a - b"),
    ("divide return a / b", "calculator.py", "return a / b"),
]


def evaluate(service: Service, provider="demo", approve=False):
    repo = service.import_repository("demo://calculator")
    chunks = service.repository(repo["id"]).chunks
    retrieval = {}
    for mode in ["keyword", "vector", "hybrid"]:
        recalls, reciprocal, details = [], [], []
        for query, path, marker in QUERIES:
            relevant = {c["id"] for c in chunks if c["path"] == path and marker in c["text"]}
            hits = service.retrieve(repo["id"], query, mode, 5)
            ranks = [i + 1 for i, hit in enumerate(hits) if hit["id"] in relevant]
            recall = len({h["id"] for h in hits} & relevant) / len(relevant)
            rr = 1 / ranks[0] if ranks else 0
            recalls.append(recall)
            reciprocal.append(rr)
            details.append(
                {
                    "query": query,
                    "relevant_chunk_ids": sorted(relevant),
                    "retrieved_chunk_ids": [h["id"] for h in hits],
                    "recall_at_5": recall,
                    "rr": rr,
                }
            )
        retrieval[mode] = {
            "recall_at_5": sum(recalls) / len(recalls),
            "mrr": sum(reciprocal) / len(reciprocal),
            "queries": details,
        }
    runs = []
    for variant in "ABCD":
        started = time.monotonic()
        task = service.create_task(
            TaskRequest(
                repository_id=repo["id"],
                provider=provider,
                variant=variant,
                prompt="Fix add so it returns the sum of two numbers. Preserve tests.",
            )
        )
        service.execute(task["id"])
        task = service.task(task["id"])
        requested_approval = task["status"] == "awaiting_approval"
        if requested_approval and approve:
            service.decide(
                task["id"], {"approved": True, "patch_digest": task["result"]["patch"]["digest"]}
            )
            service.execute(task["id"])
            task = service.task(task["id"])
        test_status = task["result"].get("test_result", {}).get("status", "not_run")
        runs.append(
            {
                "variant": variant,
                "task_id": task["id"],
                "status": task["status"],
                "latency_seconds": round(time.monotonic() - started, 4),
                "approval_requested": requested_approval,
                "automated_approval": approve and requested_approval,
                "patch_test_pass": True
                if test_status == "passed"
                else False
                if test_status in {"failed", "timeout"}
                else None,
                "task_success": True
                if task["status"] == "completed"
                else None
                if test_status == "not_run"
                else False,
                "usage": task["result"].get("usage"),
                "test_result": task["result"].get("test_result"),
            }
        )
    return {
        "dataset": "bundled-calculator-smoke-v1",
        "commit": repo["commit"],
        "provider": provider,
        "embedding": service.settings.embedding_provider,
        "retrieval": retrieval,
        "agent_runs": runs,
        "failure_recovery_rate": None,
        "human_intervention_rate": None,
        "limitations": [
            "One synthetic self-owned bug, six retrieval queries: not a general benchmark.",
            "Demo proposals are deterministic fixtures, not measurements of LLM quality.",
            "Null means unmeasured; script approvals are not human interventions.",
            "A-D share safety/approval gates; D additionally uses Deep Agents in real-model mode.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["demo", "openai"], default="demo")
    parser.add_argument(
        "--approve", action="store_true", help="Approve bundled benchmark patches automatically"
    )
    parser.add_argument("--output", default="../benchmarks/results/smoke.json")
    args = parser.parse_args()
    settings = Settings()
    with tempfile.TemporaryDirectory(prefix="devpilot-benchmark-") as temporary:
        settings.data_dir = Path(temporary)
        settings.database_url = ""
        settings.checkpoint_url = ""
        service = Service(settings)
        try:
            result = evaluate(service, args.provider, args.approve)
        finally:
            service.close()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote real smoke results to {output.resolve()}")


if __name__ == "__main__":
    main()
