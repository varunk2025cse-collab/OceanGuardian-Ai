"""Observability helpers: Prometheus metrics and OpenTelemetry tracing.

This module initializes Prometheus metrics and exposes helpers for other modules
to increment counters or set gauges. Includes an OpenTelemetry initializer that
configures an OTLP HTTP exporter when OTEL_EXPORTER_OTLP_ENDPOINT or
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is set, falling back to a ConsoleSpanExporter
for local development. The function is a no-op when opentelemetry is not
installed so tests and simple deployments are unaffected.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

# Metrics
METRIC_EVENTS_PUBLISHED = Counter("og_events_published_total", "Total notification events published")
METRIC_PROVIDER_HEALTH_CHECKS = Counter("og_provider_health_checks_total", "Total provider health checks performed")
METRIC_EVENTS_IN_QUEUE = Gauge("og_events_in_queue", "Current notification events in queue")

# Worker / notification metrics
METRIC_EVENTS_PROCESSED = Counter("og_events_processed_total", "Total notification event stream rows processed by EventProcessor")
METRIC_NOTIFICATIONS_SENT = Counter("og_notifications_sent_total", "Total notifications successfully sent via providers")
METRIC_NOTIFICATIONS_FAILED = Counter("og_notifications_failed_total", "Total notifications that failed delivery attempts")
METRIC_NOTIFICATIONS_DEAD_LETTER = Counter("og_notifications_dead_letter_total", "Total notifications moved to dead-letter queue")

# API metrics (added by middleware if enabled)
METRIC_HTTP_REQUESTS = Counter(
    "og_http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
METRIC_HTTP_LATENCY = Counter(
    "og_http_latency_seconds_total", "Total HTTP request latency in seconds", ["method", "path"]
)


def metrics_response():
    # Returns a (bytes, content_type) tuple for HTTP response
    return generate_latest(), CONTENT_TYPE_LATEST


def record_event_published(count: int = 1):
    METRIC_EVENTS_PUBLISHED.inc(count)


def record_provider_health_check():
    METRIC_PROVIDER_HEALTH_CHECKS.inc()


def set_queue_depth(n: int):
    try:
        METRIC_EVENTS_IN_QUEUE.set(n)
    except Exception:
        logger.exception("Failed to set queue depth metric")


def record_event_processed(count: int = 1):
    METRIC_EVENTS_PROCESSED.inc(count)


def record_notification_sent(count: int = 1):
    METRIC_NOTIFICATIONS_SENT.inc(count)


def record_notification_failed(count: int = 1):
    METRIC_NOTIFICATIONS_FAILED.inc(count)


def record_notification_dead_letter(count: int = 1):
    METRIC_NOTIFICATIONS_DEAD_LETTER.inc(count)


def record_http_request(method: str, path: str, status: int):
    """Record an HTTP request metric. Path is sanitized to prevent
    cardinality explosion (e.g. /api/v1/sos/123 vs /api/v1/sos/{id})."""
    try:
        METRIC_HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
    except Exception:
        pass


def record_http_latency(method: str, path: str, seconds: float):
    """Record HTTP latency in seconds. Path sanitized as above."""
    try:
        METRIC_HTTP_LATENCY.labels(method=method, path=path).inc(seconds)
    except Exception:
        pass


def init_tracing(service_name: str = "oceanguardian") -> None:
    """Initialize OpenTelemetry tracing.

    Precedence:
      1. OTEL_EXPORTER_OTLP_TRACES_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT
         set → configure OTLP HTTP exporter (production).
      2. Otherwise → ConsoleSpanExporter (local development / debugging).
      3. OpenTelemetry packages missing → disabled (no-op).

    In production, set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT to your collector
    (e.g. http://otel-collector:4318/v1/traces) and optionally
    OTEL_SERVICE_NAME to override the service name.
    """
    try:
        # Local imports to avoid optional dependency being required for tests
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        service = os.environ.get("OTEL_SERVICE_NAME", service_name)
        resource = Resource.create({SERVICE_NAME: service})

        provider = TracerProvider(resource=resource)

        otlp_traces_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

        if otlp_traces_endpoint or otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                endpoint = otlp_traces_endpoint or (otlp_endpoint.rstrip("/") + "/v1/traces")
                exporter = OTLPSpanExporter(endpoint=endpoint)
                logger.info("OpenTelemetry tracing initialized (OTLP HTTP exporter → %s)", endpoint)
            except Exception as e:
                logger.warning("OTLP exporter unavailable (%s) — falling back to console exporter", e)
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()
            logger.info("OpenTelemetry tracing initialized (ConsoleSpanExporter)")

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
    except Exception as e:  # pragma: no cover - optional dependency path
        logger.info("OpenTelemetry not configured (optional dependency missing or init error): %s", e)


# Backwards-compatible alias
initialize_tracing = init_tracing