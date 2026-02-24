"""
OpenTelemetry Initialization
=============================
Instruments FastAPI, httpx, and logging with OTLP trace export
and Prometheus metrics endpoint.

Enable via env: OTEL_ENABLED=true
"""

import os
import logging

logger = logging.getLogger("Telemetry")


def _env_bool(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


OTEL_ENABLED = _env_bool("OTEL_ENABLED", "false")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "reg01-backend")
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_METRICS_PORT = int(os.getenv("OTEL_METRICS_PORT", "9464"))


# Custom metric recorders (no-op when OTEL disabled)
_llm_duration_histogram = None
_llm_tokens_counter = None
_queue_depth_gauge = None
_cache_hit_counter = None
_cache_miss_counter = None


def init_telemetry(app):
    """Initialize OpenTelemetry if enabled. Call at app startup."""
    global _llm_duration_histogram, _llm_tokens_counter
    global _queue_depth_gauge, _cache_hit_counter, _cache_miss_counter

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED != true)")
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from prometheus_client import start_http_server

        resource = Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})

        # Traces
        tracer_provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Metrics
        prometheus_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
        metrics.set_meter_provider(meter_provider)

        meter = metrics.get_meter("reg01")
        _llm_duration_histogram = meter.create_histogram(
            "llm.request.duration", unit="s", description="LLM request duration"
        )
        _llm_tokens_counter = meter.create_counter(
            "llm.tokens.total", description="Total LLM tokens used"
        )
        _queue_depth_gauge = meter.create_up_down_counter(
            "queue.depth", description="Current queue depth"
        )
        _cache_hit_counter = meter.create_counter(
            "cache.hits", description="Cache hit count"
        )
        _cache_miss_counter = meter.create_counter(
            "cache.misses", description="Cache miss count"
        )

        # Auto-instrument
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        LoggingInstrumentor().instrument(set_logging_format=True)

        # Start Prometheus metrics HTTP server
        start_http_server(OTEL_METRICS_PORT)

        logger.info(
            "OpenTelemetry initialized: service=%s, otlp=%s, metrics_port=%d",
            OTEL_SERVICE_NAME, OTEL_EXPORTER_ENDPOINT, OTEL_METRICS_PORT,
        )

    except Exception as exc:
        logger.warning("Failed to initialize OpenTelemetry: %s", exc)


# ─── Metric Recording Helpers ────────────────────────────────────────────────

def record_llm_duration(duration_s: float, provider: str = "", model: str = ""):
    if _llm_duration_histogram:
        _llm_duration_histogram.record(duration_s, {"provider": provider, "model": model})


def record_llm_tokens(total: int, provider: str = "", model: str = ""):
    if _llm_tokens_counter:
        _llm_tokens_counter.add(total, {"provider": provider, "model": model})


def record_queue_depth_change(delta: int):
    if _queue_depth_gauge:
        _queue_depth_gauge.add(delta)


def record_cache_hit(cache_type: str = "faq"):
    if _cache_hit_counter:
        _cache_hit_counter.add(1, {"type": cache_type})


def record_cache_miss(cache_type: str = "faq"):
    if _cache_miss_counter:
        _cache_miss_counter.add(1, {"type": cache_type})
