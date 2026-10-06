from __future__ import annotations

import json
import logging
import threading
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID, uuid4

import requests
from fastapi import Request, Response
from sqlmodel import Session

from database import get_sql_engine
from models import InventoryAlertState
from telemetry import CONTRACTS, TELEMETRY_ENDPOINT, TelemetryEvent

logger = logging.getLogger("api.telemetry")
request_context: ContextVar[Request | None] = ContextVar("telemetry_request", default=None)


@dataclass
class QueuedEvent:
    event: TelemetryEvent
    dedup_key: str | None = None


def mark_expiry_delivered(keys: list[str]) -> None:
    if not keys:
        return
    with Session(get_sql_engine()) as session:
        for key in keys:
            if session.get(InventoryAlertState, key) is None:
                session.add(InventoryAlertState(key=key))
        session.commit()


class TelemetryDelivery:
    def __init__(self, endpoint: str = TELEMETRY_ENDPOINT):
        self.endpoint = endpoint
        self._queue: deque[QueuedEvent] = deque()
        self._keys: set[str] = set()
        self._unpersisted_keys: deque[str] = deque()
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._outstanding = 0
        self.dropped = 0

    @property
    def queued_count(self) -> int:
        with self._lock:
            return len(self._queue)

    def track(self, event: TelemetryEvent, dedup_key: str | None = None) -> bool:
        with self._lock:
            if dedup_key and dedup_key in self._keys:
                return False
            if self._outstanding >= 200:
                self.dropped += 1
                return False
            self._queue.append(QueuedEvent(event, dedup_key))
            self._outstanding += 1
            if dedup_key:
                self._keys.add(dedup_key)
            if len(self._queue) >= 20:
                self._wake.set()
            return True

    def flush(self) -> bool:
        with self._flush_lock:
            batch: list[QueuedEvent] = []
            with self._lock:
                while self._queue and len(batch) < 20:
                    candidate = [item.event.model_dump(mode="json") for item in [*batch, self._queue[0]]]
                    if len(json.dumps({"events": candidate}, separators=(",", ":")).encode()) > 48000:
                        break
                    batch.append(self._queue.popleft())
            if not batch:
                return True
            payload = {"events": [item.event.model_dump(mode="json") for item in batch]}
            delivered = False
            for attempt in range(4):
                try:
                    response = requests.post(self.endpoint, json=payload, timeout=5, allow_redirects=False)
                    receipt = response.json() if response.status_code == 200 else None
                    if isinstance(receipt, dict) and receipt.get("received") == len(batch):
                        delivered = True
                        break
                except (requests.RequestException, ValueError):
                    pass
                if attempt < 3 and self._stop.wait(2 ** attempt):
                    break
            keys = [item.dedup_key for item in batch if item.dedup_key]
            acknowledged = False
            if delivered:
                try:
                    mark_expiry_delivered(keys)
                    acknowledged = True
                except Exception:
                    logger.warning("Telemetry expiry acknowledgment failed")
            else:
                logger.warning("Telemetry batch discarded count=%d", len(batch))
            with self._lock:
                self._outstanding -= len(batch)
                if not delivered:
                    self.dropped += len(batch)
                    self._keys.difference_update(keys)
                elif acknowledged:
                    self._keys.difference_update(keys)
                else:
                    self._unpersisted_keys.extend(keys)
                    while len(self._unpersisted_keys) > 200:
                        self._keys.discard(self._unpersisted_keys.popleft())
            return delivered

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(10)
            self._wake.clear()
            if self._stop.is_set():
                break
            self.flush()
            if self.queued_count >= 20:
                self._wake.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="telemetry-delivery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=6)


service = TelemetryDelivery()


def enqueue_signal(signal: dict, request: Request | None = None) -> bool:
    request = request or request_context.get()
    if request is None:
        return False
    try:
        session_id = str(UUID(request.headers.get("X-Telemetry-Session", "")))
    except ValueError:
        session_id = str(uuid4())
    event = TelemetryEvent(
        eventId=signal["eventId"], timestamp=signal["timestamp"], sessionId=session_id,
        userId=getattr(request.state, "telemetry_user_id", f"anonymous_{uuid4()}"),
        event_type=signal["event_type"], schemaVersion=CONTRACTS[signal["event_type"]]["schemaVersion"],
        requestId=request.state.telemetry_request_id, properties=signal["properties"],
    )
    service.track(event, signal.get("_dedup_key"))
    return True


def capture_inventory_signals(request: Request, response: Response) -> None:
    raw = response.headers.get("X-Telemetry-Events")
    if raw is None:
        return
    del response.headers["X-Telemetry-Events"]
    try:
        signals = json.loads(raw)
        if not isinstance(signals, list):
            return
        for signal in signals:
            if not isinstance(signal, dict) or signal.get("_server_owned"):
                continue
            enqueue_signal(signal, request)
    except (ValueError, KeyError, TypeError):
        logger.warning("Telemetry signal discarded: contract")