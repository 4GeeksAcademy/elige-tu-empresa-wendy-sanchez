import { track } from "./telemetry";
import { validTelemetryProperties } from "./telemetryContracts";

export function recordTelemetryControl(eventType: string, properties: Record<string, unknown>): void {
  if (typeof window === "undefined" || !validTelemetryProperties(eventType, properties)) return;
  track(eventType, properties);
}