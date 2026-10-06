import { track } from "./telemetry";
import { withTelemetryEnvelope } from "./telemetryContext";

export function apiTelemetryRoute(url: string): string {
  const path = new URL(url, "http://localhost").pathname.replace(/^\/api/, "");
  if (/^\/inventory\/products\/\d+(\/policy|\/stock)?$/.test(path)) return path.replace(/\/\d+/, "/{id}");
  if (["/inventory/products", "/inventory/orders", "/inventory/orders/inbound", "/inventory/orders/outbound", "/auth/me", "/auth/login", "/profiles/me", "/suppliers", "/incidents", "/incidents/summary"].includes(path)) return path;
  return "/other";
}

export function captureApiResult(url: string, method: string, status: number, duration: number, requestId: string): void {
  if (typeof window === "undefined") return;
  const service = url.includes("/incidents") ? "incidents_api" : "healthcore_api";
  withTelemetryEnvelope({ requestId }, () => {
    const properties = { service, route_template: apiTelemetryRoute(url), method };
    if (status >= 400 || Math.random() < 0.05) track("api_latency_recorded", {
      ...properties, status_code: status, duration_ms: Math.min(300000, Math.max(0, duration)), cache_result: "not_applicable",
    });
    if (status >= 400) track("api_request_failed", {
      ...properties, status_code: status,
      error_class: status === 401 ? "authentication" : status === 403 ? "authorization" : status === 422 ? "validation" : status === 503 ? "dependency" : "internal",
      error_code: status === 503 ? "network_error" : `http_${status}`,
    });
  });
}

export function captureResponseSignals(response: Response, requestId: string): void {
  try {
    const signals: unknown = JSON.parse(response.headers.get("X-Telemetry-Events") ?? "[]");
    if (!Array.isArray(signals) || signals.length > 100) return;
    for (const value of signals) {
      if (!value || typeof value !== "object") continue;
      const event = value as { event_type?: unknown; properties?: unknown; eventId?: unknown; timestamp?: unknown };
      if (typeof event.event_type !== "string" || !event.properties || typeof event.properties !== "object"
        || typeof event.eventId !== "string" || !/^[a-f0-9-]{36}$/.test(event.eventId)
        || typeof event.timestamp !== "string" || !Number.isFinite(Date.parse(event.timestamp))) continue;
      withTelemetryEnvelope({ requestId, eventId: event.eventId, timestamp: event.timestamp }, () => {
        track(event.event_type as string, event.properties as Record<string, unknown>);
      });
    }
  } catch { return; }
}