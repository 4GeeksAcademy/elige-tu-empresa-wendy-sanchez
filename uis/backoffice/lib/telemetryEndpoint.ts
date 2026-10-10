export function browserTelemetryEndpoint(value: string | undefined): string | undefined {
  if (!value) return undefined;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return undefined;
    return ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
      ? "/api/telemetry/events" : value;
  } catch {
    return undefined;
  }
}