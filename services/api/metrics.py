"""Prometheus Metrics Collection and Exposition (Phase 2I-3).

Provides:
- Standard Prometheus text format (v0.0.4) /metrics endpoint
- In-memory lock-free request counter and latency tracker
- System operational gauges for nowcast runs, active alerts, and uptime
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Tuple

import structlog
from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Global metrics state
_START_TIME = time.time()
_REQUEST_COUNTS: Dict[Tuple[str, str, int], int] = defaultdict(int)
_REQUEST_LATENCY_SUM: Dict[Tuple[str, str], float] = defaultdict(float)
_REQUEST_LATENCY_COUNT: Dict[Tuple[str, str], int] = defaultdict(int)

metrics_router = APIRouter(tags=["Monitoring"])


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to record request duration and HTTP status codes for Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Ignore metrics endpoint itself from recursive counting
        if request.url.path == "/metrics":
            return await call_next(request)

        t0 = time.time()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - t0
            # Simplify path to reduce high-cardinality labels
            clean_path = path
            if "/ward/" in path:
                clean_path = "/api/v1/decision/ward/{id}/risk"
            elif "/citizen-reports/" in path:
                clean_path = "/api/v1/geodata/citizen-reports/{id}"
            elif "/field-ops/tasks/" in path:
                clean_path = "/api/v1/field-ops/tasks/{id}"

            _REQUEST_COUNTS[(method, clean_path, status_code)] += 1
            _REQUEST_LATENCY_SUM[(method, clean_path)] += duration
            _REQUEST_LATENCY_COUNT[(method, clean_path)] += 1

        return response


@metrics_router.get("/metrics", response_class=Response)
async def get_prometheus_metrics():
    """Expose application metrics in standard Prometheus exposition format."""
    from services.alerts.engine import get_alert_engine

    uptime = time.time() - _START_TIME
    lines = [
        "# HELP mufns_uptime_seconds Total runtime of the MUFNS application in seconds.",
        "# TYPE mufns_uptime_seconds gauge",
        f"mufns_uptime_seconds {uptime:.2f}",
        "",
        "# HELP mufns_http_requests_total Total number of HTTP requests processed.",
        "# TYPE mufns_http_requests_total counter",
    ]

    for (m, p, s), count in _REQUEST_COUNTS.items():
        lines.append(f'mufns_http_requests_total{{method="{m}",endpoint="{p}",status="{s}"}} {count}')

    lines.extend([
        "",
        "# HELP mufns_http_request_duration_seconds_total Total duration of HTTP requests in seconds.",
        "# TYPE mufns_http_request_duration_seconds_total counter",
    ])
    for (m, p), dur_sum in _REQUEST_LATENCY_SUM.items():
        cnt = _REQUEST_LATENCY_COUNT[(m, p)]
        lines.append(f'mufns_http_request_duration_seconds_total{{method="{m}",endpoint="{p}"}} {dur_sum:.4f}')
        lines.append(f'mufns_http_request_duration_seconds_count{{method="{m}",endpoint="{p}"}} {cnt}')

    # Operational metrics
    try:
        alert_eng = get_alert_engine()
        active_alerts = alert_eng.get_active_alerts()
        lines.extend([
            "",
            "# HELP mufns_active_alerts_total Current number of active flood alerts by severity.",
            "# TYPE mufns_active_alerts_total gauge",
        ])
        sev_counts = defaultdict(int)
        for a in active_alerts:
            sev_counts[a.severity.lower()] += 1
        for s in ("minor", "moderate", "severe", "extreme"):
            lines.append(f'mufns_active_alerts_total{{severity="{s}"}} {sev_counts[s]}')
    except Exception:
        pass

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
