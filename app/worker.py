from __future__ import annotations

import json
import logging
import signal
from functools import lru_cache
from threading import Event

import boto3

from app.core.config import get_settings
from app.core.google_sync_scheduler import run_google_sync_once

logger = logging.getLogger(__name__)
shutdown = Event()


@lru_cache
def sqs_client():
    settings = get_settings()
    return boto3.client("sqs", region_name=settings.aws_region)


def process_message(body: str) -> None:
    payload = json.loads(body) or {}
    if payload.get("action") != "google_metrics_sync":
        raise ValueError("Unsupported marketing worker action.")
    run_google_sync_once(get_settings())


def lambda_handler(event: dict, _context) -> dict:
    failures = []
    for record in event.get("Records", []):
        try:
            process_message(record.get("body", ""))
        except Exception:
            logger.exception("Marketing queue record failed")
            failures.append({"itemIdentifier": record.get("messageId", "")})
    return {"batchItemFailures": failures}


def poll_forever() -> None:
    settings = get_settings()
    if not settings.worker_queue_url:
        raise RuntimeError("WORKER_QUEUE_URL is required for the worker process.")
    client = sqs_client()
    while not shutdown.is_set():
        response = client.receive_message(
            QueueUrl=settings.worker_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=900,
        )
        for message in response.get("Messages", []):
            try:
                process_message(message["Body"])
            except Exception:
                logger.exception("Marketing job failed and will be retried")
                continue
            client.delete_message(
                QueueUrl=settings.worker_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    poll_forever()


if __name__ == "__main__":
    main()
