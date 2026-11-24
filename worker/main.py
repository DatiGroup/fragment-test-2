#!/usr/bin/env python3
"""Kafka consumer worker that listens to events from fragment-1.

Behavior:
- Consumes messages from KAFKA_TOPIC (default: f1.events)
- POSTs each event to the API for storage in the event_log table
- Provides an audit trail of all events received from fragment-1

Configuration via environment variables (see `.env.example`):
- KAFKA_BOOTSTRAP_SERVERS (comma-separated, required)
- KAFKA_TOPIC (default: f1.events)
- KAFKA_CONSUMER_GROUP (default: test-fragment-2-consumer)
- API_URL (default: http://localhost:8000)
- FRAGMENT_ID (default: test-fragment-2)
"""

import os
import signal
import logging
import json

from dotenv import load_dotenv
import requests

# optional kafka client
try:
    from kafka import KafkaConsumer
except Exception:
    KafkaConsumer = None

load_dotenv()

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")  # comma-separated
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "f1.events")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "test-fragment-2-consumer")

# API configuration
API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
EVENTS_ENDPOINT = f"{API_URL}/events"

FRAGMENT_ID = os.getenv("FRAGMENT_ID", "test-fragment-2")

stop_requested = False
consumer = None
session = requests.Session()
# This fragment's own API admits its worker by the instance's internal token,
# which the platform generates per fragment instance (see k8s manifest).
if os.getenv("FRAGMENT_INTERNAL_TOKEN"):
    session.headers["X-Fragment-Token"] = os.environ["FRAGMENT_INTERNAL_TOKEN"]


def _signal_handler(sig, frame):
    global stop_requested
    logging.info("Shutdown signal received")
    stop_requested = True


def process_event(event: dict) -> None:
    """Process a single event from Kafka by storing it in the API.

    POSTs the event to the /events endpoint for audit logging.

    Args:
        event: The deserialized JSON event from Kafka
    """
    logging.info("Received event: %s", event)

    # POST to the API to store in event_log
    try:
        resp = session.post(EVENTS_ENDPOINT, json=event, timeout=10)
        if resp.status_code == 201:
            logging.info("Event logged successfully: %s", event.get("event_id"))
        elif resp.status_code == 409:
            logging.warning("Duplicate event (already logged): %s", event.get("event_id"))
        else:
            logging.error("Failed to log event: %s - %s", resp.status_code, resp.text)
    except requests.RequestException as exc:
        logging.error("Error posting event to API: %s", exc)


def create_consumer():
    """Create and return a Kafka consumer instance."""
    if not KAFKA_BOOTSTRAP_SERVERS:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS is required but not set")
    if KafkaConsumer is None:
        raise RuntimeError("kafka-python is not installed")

    bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",") if s.strip()]

    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=1000,  # Return from poll after 1 second to check stop_requested
    )


def main() -> None:
    global consumer, stop_requested

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Worker starting (listening to topic=%s; group=%s)", KAFKA_TOPIC, KAFKA_CONSUMER_GROUP)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        consumer = create_consumer()
        logging.info("Connected to Kafka at %s", KAFKA_BOOTSTRAP_SERVERS)
    except Exception as exc:
        logging.error("Failed to create Kafka consumer: %s", exc)
        return

    while not stop_requested:
        try:
            # Poll for messages (returns after consumer_timeout_ms if no messages)
            for message in consumer:
                if stop_requested:
                    break
                try:
                    process_event(message.value)
                except Exception as exc:
                    logging.error("Error processing message: %s", exc)
        except Exception as exc:
            if not stop_requested:
                logging.warning("Consumer error: %s", exc)

    # graceful shutdown
    try:
        if consumer is not None:
            consumer.close()
            logging.info("Kafka consumer closed")
    except Exception as exc:
        logging.warning("Error closing Kafka consumer: %s", exc)

    logging.info("Worker shutting down")


if __name__ == "__main__":
    main()
