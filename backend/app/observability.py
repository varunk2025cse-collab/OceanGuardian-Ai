"""Observability helpers: Prometheus metrics and OpenTelemetry stub.

This module initializes Prometheus metrics and exposes helpers for other modules
to increment counters or set gauges. Includes a lightweight OpenTelemetry
initializer that configures a console exporter if OpenTelemetry packages are
available. The function is a no-op when opentelemetry is not installed so tests
and simple deployments are unaffected.
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


def init_tracing(service_name: str = "oceanguardian") -> None:
    """Attempt to initialize OpenTelemetry tracing.

    This is best-effort: if opentelemetry packages are missing, it logs a
    message and leaves tracing disabled. When present, it configures a
    simple ConsoleSpanExporter and BatchSpanProcessor. In production,
    environment variables (e.g. OTEL_EXPORTER_OTLP_ENDPOINT) can be used to
    configure different exporters.
    """
    try:
        # Local imports to avoid optional dependency being required for tests
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        # Use OTEL_* environment variables if present in the environment.
        # For now, configure a ConsoleSpanExporter which is safe in most dev/test envs.
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry tracing initialized (ConsoleSpanExporter)")
    except Exception as e:  # pragma: no cover - optional dependency path
        logger.info("OpenTelemetry not configured (optional dependency missing or init error): %s", e)


# Backwards-compatible alias
initialize_tracing = init_tracing
