from __future__ import annotations

import csv
import json
import os
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from load_tester.core.client import ErrorKind, RequestResult
from load_tester.core.config import settings


class TestStatus(str, Enum):
    idle = "idle"
    running = "running"
    finished = "finished"


@dataclass
class ErrorEntry:
    ts: float
    endpoint: str
    status_code: int
    error_kind: str
    worker_id: int
    message: str


@dataclass
class RealtimeSnapshot:
    ts: float
    elapsed_s: float
    workers_active: int
    rps: float
    error_rate_pct: float
    throughput_kbps: float
    p50: float
    p95: float
    p99: float
    total_requests: int
    total_errors: int


@dataclass
class EndpointStats:
    endpoint: str
    requests: int = 0
    errors: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def rps(self) -> float:
        return 0.0

    @property
    def error_pct(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.errors / self.requests * 100

    def percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * p / 100)
        return sorted_l[min(idx, len(sorted_l) - 1)]


class MetricsStore:
    """Thread-safe metrics collector. Singleton shared between runner and dashboard."""

    _instance: "MetricsStore | None" = None

    def __new__(cls) -> "MetricsStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.status = TestStatus.idle
        self.scenario_name: str = ""
        self.started_at: float = 0.0
        self.finished_at: float = 0.0
        self.duration_s: float = 0.0
        self.workers_active: int = 0
        self.max_workers_reached: int = 0

        # All recorded results (bounded to avoid unbounded memory)
        self._all: deque[RequestResult] = deque(maxlen=500_000)

        # Sliding window for real-time stats
        self._window: deque[RequestResult] = deque()

        # Per-endpoint accumulated stats
        self._endpoint_stats: dict[str, EndpointStats] = defaultdict(lambda: EndpointStats(""))

        # Recent errors (last 200)
        self._recent_errors: deque[ErrorEntry] = deque(maxlen=200)

        # Time-series snapshots (one per second) for report export
        self._snapshots: list[RealtimeSnapshot] = []

    def reset(self) -> None:
        self._init()

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def record(self, result: RequestResult) -> None:
        now = time.time()
        self._all.append(result)
        self._window.append(result)

        key = f"{result.method} {result.endpoint}"
        stats = self._endpoint_stats[key]
        stats.endpoint = key
        stats.requests += 1
        stats.latencies.append(result.latency_ms)
        if result.is_error:
            stats.errors += 1

        if result.is_error:
            self._recent_errors.append(
                ErrorEntry(
                    ts=result.started_at,
                    endpoint=f"{result.method} {result.endpoint}",
                    status_code=result.status_code,
                    error_kind=result.error_kind.value,
                    worker_id=result.worker_id,
                    message=result.error_message,
                )
            )

        self._evict_window(now)

    def _evict_window(self, now: float) -> None:
        cutoff = now - settings.metrics_window_s
        while self._window and self._window[0].started_at < cutoff:
            self._window.popleft()

    # ── Real-time metrics ──────────────────────────────────────────────────────

    def snapshot(self) -> RealtimeSnapshot:
        now = time.time()
        self._evict_window(now)
        elapsed = now - self.started_at if self.started_at else 0.0
        window = list(self._window)
        latencies = [r.latency_ms for r in window]

        rps = len(window) / settings.metrics_window_s if window else 0.0
        errors = sum(1 for r in window if r.is_error)
        error_rate = errors / len(window) * 100 if window else 0.0
        throughput = sum(r.response_bytes for r in window) / settings.metrics_window_s / 1024

        snap = RealtimeSnapshot(
            ts=now,
            elapsed_s=elapsed,
            workers_active=self.workers_active,
            rps=round(rps, 2),
            error_rate_pct=round(error_rate, 2),
            throughput_kbps=round(throughput, 2),
            p50=round(_percentile(latencies, 50), 2),
            p95=round(_percentile(latencies, 95), 2),
            p99=round(_percentile(latencies, 99), 2),
            total_requests=len(self._all),
            total_errors=sum(1 for r in self._all if r.is_error),
        )
        self._snapshots.append(snap)
        return snap

    # ── Accessors for dashboard ────────────────────────────────────────────────

    def recent_errors(self) -> list[ErrorEntry]:
        return list(self._recent_errors)

    def endpoint_table(self) -> list[dict[str, Any]]:
        rows = []
        for key, stats in self._endpoint_stats.items():
            rows.append({
                "endpoint": key,
                "requests": stats.requests,
                "errors": stats.errors,
                "error_pct": round(stats.error_pct, 2),
                "p50": round(stats.percentile(50), 2),
                "p95": round(stats.percentile(95), 2),
                "p99": round(stats.percentile(99), 2),
            })
        return sorted(rows, key=lambda r: r["requests"], reverse=True)

    # ── Final report ───────────────────────────────────────────────────────────

    def build_report(self) -> dict[str, Any]:
        all_results = list(self._all)
        latencies = [r.latency_ms for r in all_results]
        errors_by_kind: dict[str, int] = defaultdict(int)
        for r in all_results:
            if r.is_error:
                errors_by_kind[r.error_kind.value] += 1

        by_endpoint = self.endpoint_table()
        slowest = max(by_endpoint, key=lambda e: e["p95"], default=None)
        fastest = min(by_endpoint, key=lambda e: e["p95"], default=None)
        most_errors = max(by_endpoint, key=lambda e: e["error_pct"], default=None)

        total_duration = (self.finished_at or time.time()) - (self.started_at or time.time())
        avg_rps = len(all_results) / total_duration if total_duration > 0 else 0

        # Histogram buckets
        buckets = {"<50ms": 0, "50-100ms": 0, "100-250ms": 0, "250-500ms": 0, "500ms-1s": 0, ">1s": 0}
        for l in latencies:
            if l < 50:
                buckets["<50ms"] += 1
            elif l < 100:
                buckets["50-100ms"] += 1
            elif l < 250:
                buckets["100-250ms"] += 1
            elif l < 500:
                buckets["250-500ms"] += 1
            elif l < 1000:
                buckets["500ms-1s"] += 1
            else:
                buckets[">1s"] += 1

        return {
            "scenario": self.scenario_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": round(total_duration, 2),
            "max_workers": self.max_workers_reached,
            "total_requests": len(all_results),
            "total_errors": sum(errors_by_kind.values()),
            "errors_by_kind": dict(errors_by_kind),
            "avg_rps": round(avg_rps, 2),
            "peak_rps": round(max((s.rps for s in self._snapshots), default=0), 2),
            "latency": {
                "min": round(min(latencies, default=0), 2),
                "max": round(max(latencies, default=0), 2),
                "mean": round(statistics.mean(latencies) if latencies else 0, 2),
                "p50": round(_percentile(latencies, 50), 2),
                "p95": round(_percentile(latencies, 95), 2),
                "p99": round(_percentile(latencies, 99), 2),
            },
            "histogram": buckets,
            "slowest_endpoint": slowest,
            "fastest_endpoint": fastest,
            "most_errors_endpoint": most_errors,
            "endpoints": by_endpoint,
        }

    def save_report(self) -> tuple[str, str]:
        """Save JSON and CSV reports. Returns (json_path, csv_path)."""
        os.makedirs(settings.results_dir, exist_ok=True)
        ts = int(self.finished_at or time.time())
        report = self.build_report()

        json_path = os.path.join(settings.results_dir, f"report_{ts}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        csv_path = os.path.join(settings.results_dir, f"report_{ts}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["elapsed_s", "workers_active", "rps", "p50", "p95", "p99", "error_rate_pct", "throughput_kbps", "total_requests", "total_errors"])
            for snap in self._snapshots:
                writer.writerow([
                    round(snap.elapsed_s, 1),
                    snap.workers_active,
                    snap.rps,
                    snap.p50,
                    snap.p95,
                    snap.p99,
                    snap.error_rate_pct,
                    snap.throughput_kbps,
                    snap.total_requests,
                    snap.total_errors,
                ])

        return json_path, csv_path


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# Module-level singleton
metrics_store = MetricsStore()
