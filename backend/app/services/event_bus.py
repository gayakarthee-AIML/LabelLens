"""
Kafka-ready event bus.

The brief asks for a "Kafka architecture-ready" event layer without requiring
a live Kafka cluster for the prototype to run locally. `EventBus.publish` is
the single call site the rest of the app uses; when KAFKA_ENABLED=false (the
default) it logs and no-ops, and when true it produces to the configured
topic with `confluent-kafka` / `kafka-python` (add whichever client you
prefer to requirements.txt — intentionally not pinned here since no broker
is available to test against in this environment).
"""
import json
import logging

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("labellens.events")

_producer = None


def _get_producer():
    global _producer
    if not settings.kafka_enabled:
        return None
    if _producer is None:
        from kafka import KafkaProducer  # add kafka-python to requirements.txt to enable

        _producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    return _producer


def publish(topic: str, payload: dict) -> None:
    producer = _get_producer()
    if producer is None:
        logger.info("event_bus (no-op, KAFKA_ENABLED=false): topic=%s payload=%s", topic, payload)
        return
    producer.send(topic, value=payload)
