#!/usr/bin/env python3
"""Safe interview concurrency load-test harness (Phase 4).

Default mode is dry-run planning only. Live HTTP calls require --confirm-live
and are capped at --max-concurrent (default 5). High-volume production runs
(25/50) require explicit operator approval and Azure quota confirmation.

Measures (when live): API latency p50/p95, error rate, optional health snapshot.
Does not send raw audio/PII to logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

SAFE_DEFAULT_MAX = 5
APPROVAL_REQUIRED_AT = 10


@dataclass
class ScenarioResult:
    concurrent: int
    samples: list[float] = field(default_factory=list)
    errors: int = 0
    throttles: int = 0

    def summary(self) -> dict[str, Any]:
        vals = sorted(self.samples)
        n = len(vals)

        def pct(p: float) -> float | None:
            if not vals:
                return None
            idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
            return round(vals[idx], 2)

        return {
            "concurrent": self.concurrent,
            "requests": n + self.errors,
            "ok": n,
            "errors": self.errors,
            "throttles_429": self.throttles,
            "p50_ms": pct(50),
            "p95_ms": pct(95),
            "mean_ms": round(statistics.mean(vals), 2) if vals else None,
            "max_ms": round(max(vals), 2) if vals else None,
        }


def plan_matrix(max_concurrent: int) -> list[int]:
    ladder = [1, 5, 10, 25, 50]
    return [n for n in ladder if n <= max_concurrent]


async def _probe_health(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    try:
        r = await client.get(f"{base.rstrip('/')}/health", timeout=10.0)
        if r.status_code == 200:
            return r.json() if r.content else {"status": "ok"}
        return {"status": "error", "http": r.status_code}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:120]}


async def _one_turn(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> tuple[float, int]:
    t0 = time.perf_counter()
    response = await client.post(url, headers=headers, json={"probe": True}, timeout=60.0)
    ms = (time.perf_counter() - t0) * 1000.0
    return ms, int(response.status_code)


async def run_scenario(
    *,
    base: str,
    path: str,
    concurrent: int,
    token: str | None,
    turns: int,
) -> ScenarioResult:
    result = ScenarioResult(concurrent=concurrent)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{base.rstrip('/')}{path}"
    limits = httpx.Limits(max_connections=max(10, concurrent * 2), max_keepalive_connections=concurrent)
    async with httpx.AsyncClient(limits=limits) as client:
        sem = asyncio.Semaphore(concurrent)

        async def worker() -> None:
            async with sem:
                try:
                    ms, status = await _one_turn(client, url, headers)
                    if status == 429:
                        result.throttles += 1
                        result.errors += 1
                    elif status >= 400:
                        result.errors += 1
                    else:
                        result.samples.append(ms)
                except Exception:
                    result.errors += 1

        await asyncio.gather(*(worker() for _ in range(max(1, turns))))
    return result


def print_plan(levels: list[int]) -> None:
    print("Phase 4 load-test plan (dry-run — no live traffic)")
    print("=" * 60)
    metrics = [
        "API response time (p50/p95)",
        "STT latency (from X-Interview / latency_trace)",
        "GPT-4o latency",
        "TTS latency / TTFA",
        "Error rate + Azure 429 throttling",
        "CPU/RAM (VM metrics)",
        "Redis queue depth (/health interview_eval_queue)",
        "DB pool wait (Postgres + app logs)",
    ]
    for n in levels:
        print(f"\nScenario: {n} concurrent interview(s)")
        print("  Measure:")
        for m in metrics:
            print(f"    - {m}")
        if n >= APPROVAL_REQUIRED_AT:
            print("  NOTE: requires explicit approval + Azure quota check before live run")
    print("\nRecommended progression: 1 → 5 → 10, then pause for quota review.")
    print("Do not run 25/50 against production without written approval.")


async def main_async(args: argparse.Namespace) -> int:
    levels = plan_matrix(args.max_concurrent)
    if not args.confirm_live:
        print_plan(levels)
        print("\nTo execute live probes (capped):")
        print(
            f"  python scripts/load_test_interview_concurrency.py "
            f"--confirm-live --base-url {args.base_url} "
            f"--path {args.path} --max-concurrent {min(SAFE_DEFAULT_MAX, args.max_concurrent)}"
        )
        return 0

    if args.max_concurrent > SAFE_DEFAULT_MAX and not args.allow_high:
        print(
            f"Refusing live run above {SAFE_DEFAULT_MAX} without --allow-high "
            "(and operator approval for Azure capacity).",
            file=sys.stderr,
        )
        return 2

    report: dict[str, Any] = {
        "base_url": args.base_url,
        "path": args.path,
        "max_concurrent": args.max_concurrent,
        "scenarios": [],
        "health_before": None,
        "health_after": None,
    }
    async with httpx.AsyncClient() as client:
        report["health_before"] = await _probe_health(client, args.base_url)

    for n in levels:
        print(f"Running concurrent={n} …")
        scenario = await run_scenario(
            base=args.base_url,
            path=args.path,
            concurrent=n,
            token=args.token,
            turns=args.turns_per_level * n,
        )
        summary = scenario.summary()
        report["scenarios"].append(summary)
        print(json.dumps(summary, indent=2))

    async with httpx.AsyncClient() as client:
        report["health_after"] = await _probe_health(client, args.base_url)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"Wrote {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8030")
    p.add_argument(
        "--path",
        default="/health/live",
        help="Probe path. Default /health/live is safe. Use a real interview endpoint only in staging.",
    )
    p.add_argument("--token", default=None, help="Optional Bearer token")
    p.add_argument("--max-concurrent", type=int, default=SAFE_DEFAULT_MAX)
    p.add_argument("--turns-per-level", type=int, default=3)
    p.add_argument("--confirm-live", action="store_true")
    p.add_argument(
        "--allow-high",
        action="store_true",
        help=f"Permit live runs above {SAFE_DEFAULT_MAX} concurrent (requires approval).",
    )
    p.add_argument("--out", default=None, help="Optional JSON report path")
    return p


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
