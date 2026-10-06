import logging

from fastapi import APIRouter

from telemetry import TelemetryBatch, TelemetryReceipt

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger("api.telemetry")


@router.post("/events", response_model=TelemetryReceipt)
def receive_events(batch: TelemetryBatch) -> TelemetryReceipt:
    logger.info("Telemetry received=%d event_types=%s", len(batch.events), [event.event_type for event in batch.events])
    return TelemetryReceipt(received=len(batch.events))