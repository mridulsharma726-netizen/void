"""
VOID Telemetry & Observability Engine
=====================================

Provides local OpenTelemetry request tracing (ConsoleExporter)
and exposes Prometheus metrics client registry for scrapers.
"""

import time
import logging
from typing import Tuple

logger = logging.getLogger("void.core.observability.telemetry")

# Initialize OpenTelemetry basic tracers
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider()
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    tracer = trace.get_tracer("void.telemetry")
    logger.info("[TELEMETRY] OpenTelemetry Tracing initialized successfully.")
except Exception as e:
    logger.error(f"[TELEMETRY] Failed to initialize OpenTelemetry: {e}")
    tracer = None

# Initialize Prometheus Metrics
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY

    # Use default registry or a dedicated one
    registry = REGISTRY

    # 1. Chat pipeline metrics
    CHAT_LATENCY = Histogram(
        "void_chat_latency_seconds", 
        "Latency of chat request handling in seconds",
        registry=registry
    )
    CHAT_REQUESTS = Counter(
        "void_chat_requests_total", 
        "Total chat requests", 
        ["intent", "status"],
        registry=registry
    )

    # 2. Automation metrics
    AUTOMATION_EXECUTIONS = Counter(
        "void_automation_executions_total", 
        "Total automated executions", 
        ["action", "status"],
        registry=registry
    )

    # 3. Voice I/O metrics
    VOICE_LATENCY = Histogram(
        "void_voice_latency_seconds", 
        "Latency of voice tasks in seconds", 
        ["phase"],
        registry=registry
    )
    WAKE_WORD_TRIGGERS = Counter(
        "void_wake_word_triggers_total", 
        "Total wake word trigger detections",
        registry=registry
    )

    # 4. Ollama model metrics
    OLLAMA_CALLS = Counter(
        "void_ollama_calls_total", 
        "Total Ollama server requests", 
        ["model", "status"],
        registry=registry
    )
    
    logger.info("[TELEMETRY] Prometheus client metrics successfully registered.")
except Exception as e:
    logger.error(f"[TELEMETRY] Failed to register Prometheus metrics: {e}")

def get_metrics_payload() -> Tuple[str, str]:
    """Generates the latest Prometheus metrics in standard text format."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest().decode("utf-8"), CONTENT_TYPE_LATEST
    except Exception as e:
        logger.error(f"[TELEMETRY] Failed to generate metrics payload: {e}")
        return "# Error generating metrics", "text/plain"
