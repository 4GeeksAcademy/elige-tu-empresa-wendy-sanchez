import { getTelemetrySession } from "./telemetrySession";
import { telemetryEnvelopeContext } from "./telemetryContext";
import { browserTelemetryEndpoint } from "./telemetryEndpoint";
import { recordTelemetryControl } from "./TelemetryService.control";
import {
  TELEMETRY_MAX_EVENT_BYTES, telemetrySchemaVersion, validTelemetryProperties, registeredTelemetryEvent,
} from "./telemetryContracts";

interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: Record<string, unknown>;
}
interface PendingBatch {
  events: TelemetryEvent[];
  retries: number;
}

const BATCH_SIZE = 20;
const FLUSH_INTERVAL_MS = 10_000;
const MAX_BATCH_BYTES = 48_000;
const MAX_QUEUE_SIZE = 200;
const MAX_RETRIES = 3;
const endpoint = browserTelemetryEndpoint(process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT);
const queue: TelemetryEvent[] = [];
let pending: PendingBatch | undefined;
let sending = false;
let started = false;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let controller: AbortController | undefined;
const counters = { dropped: 0, deliveryFailed: 0 };

function takeBatch(): TelemetryEvent[] {
  const events: TelemetryEvent[] = [];
  while (queue.length && events.length < BATCH_SIZE) {
    if (new Blob([JSON.stringify({ events: [...events, queue[0]] })]).size > MAX_BATCH_BYTES) break;
    events.push(queue.shift()!);
  }
  return events;
}

async function flush(): Promise<void> {
  if (!endpoint || sending || retryTimer) return;
  if (!pending) {
    const events = takeBatch();
    if (!events.length) return;
    pending = { events, retries: 0 };
  }
  const batch = pending;
  sending = true;
  const abortController = new AbortController();
  controller = abortController;
  const timeout = setTimeout(() => abortController.abort(), FLUSH_INTERVAL_MS);
  try {
    const response = await fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch.events }), signal: abortController.signal,
      credentials: endpoint.startsWith("/") ? "same-origin" : "omit",
    });
    if (!response.ok) throw new Error("telemetry_delivery_failed");
    if (pending === batch) pending = undefined;
  } catch {
    if (pending !== batch) return;
    if (batch.retries >= MAX_RETRIES) {
      recordTelemetryControl("telemetry_delivery_failed", { producer: "backoffice", destination: "telemetry_collector", failure_code: "unavailable", retry_count: 3, batch_size: batch.events.length });
      recordTelemetryControl("api_retry_exhausted", { service: "backoffice", dependency: "telemetry_collector", operation: "publish", attempt_count: 4, failure_code: "unavailable" });
      counters.deliveryFailed += batch.events.length;
      pending = undefined;
    } else {
      const delay = 1000 * 2 ** batch.retries;
      batch.retries += 1;
      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        void flush();
      }, delay);
    }
  } finally {
    clearTimeout(timeout);
    sending = false;
    if (!pending && queue.length >= BATCH_SIZE) void flush();
  }
}

function beacon(events: TelemetryEvent[]): boolean {
  try {
    return navigator.sendBeacon(endpoint!, new Blob([
      JSON.stringify({ events }),
    ], { type: "application/json" }));
  } catch {
    return false;
  }
}

function flushBeacon(): void {
  if (!endpoint || typeof navigator.sendBeacon !== "function") return;
  if (pending) {
    if (!beacon(pending.events)) return;
    pending = undefined;
    clearTimeout(retryTimer);
    retryTimer = undefined;
    controller?.abort();
  }
  while (queue.length) {
    const events = takeBatch();
    if (!beacon(events)) {
      queue.unshift(...events);
      return;
    }
  }
}

function onVisibilityChange(): void {
  if (document.visibilityState === "hidden") flushBeacon();
}

function start(): void {
  if (started) return;
  started = true;
  setInterval(() => { void flush(); }, FLUSH_INTERVAL_MS);
  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("pagehide", flushBeacon);
}

export function track(eventType: string, properties: Record<string, unknown>): void {
  if (typeof window === "undefined" || !endpoint) return;
  try {
    if (!validTelemetryProperties(eventType, properties)) {
      counters.dropped += 1;
      recordTelemetryControl("telemetry_event_dropped", { producer: "backoffice", event_type: registeredTelemetryEvent(eventType) ? eventType : "unknown_event", drop_reason: "schema_invalid", schema_version: telemetrySchemaVersion(eventType), count_bucket: "1" });
      return;
    }
    const session = getTelemetrySession();
    if (!session) {
      counters.dropped += 1;
      return;
    }
    const event: TelemetryEvent = {
      ...session, eventId: telemetryEnvelopeContext()?.eventId ?? crypto.randomUUID(),
      timestamp: telemetryEnvelopeContext()?.timestamp ?? new Date().toISOString(),
      event_type: eventType, schemaVersion: telemetrySchemaVersion(eventType),
      requestId: telemetryEnvelopeContext()?.requestId ?? crypto.randomUUID(), properties: { ...properties },
    };
    if (new Blob([JSON.stringify(event)]).size > TELEMETRY_MAX_EVENT_BYTES
      || queue.length + (pending?.events.length ?? 0) >= MAX_QUEUE_SIZE) {
      counters.dropped += 1;
      recordTelemetryControl("telemetry_event_dropped", { producer: "backoffice", event_type: eventType, drop_reason: "sampling_limit", schema_version: event.schemaVersion, count_bucket: "1" });
      return;
    }
    queue.push(event);
    start();
    if (queue.length >= BATCH_SIZE) void flush();
  } catch {
    counters.dropped += 1;
  }
}