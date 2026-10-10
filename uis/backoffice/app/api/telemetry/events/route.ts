import { forwardTelemetryBatch } from "../../../../lib/TelemetryService.server";

export async function POST(request: Request): Promise<Response> {
  const configured = process.env.TELEMETRY_ENDPOINT ?? process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
  let endpoint: URL;
  try {
    endpoint = configured && !configured.startsWith("/")
      ? new URL(configured)
      : new URL("/telemetry/events", process.env.SUPPLIERS_API_URL ?? "http://127.0.0.1:8000");
    if (!process.env.TELEMETRY_ENDPOINT && process.env.SUPPLIERS_API_URL
      && ["localhost", "127.0.0.1", "[::1]"].includes(endpoint.hostname)) {
      endpoint = new URL(`${endpoint.pathname}${endpoint.search}`, process.env.SUPPLIERS_API_URL);
    }
    if (!["http:", "https:"].includes(endpoint.protocol)) throw new Error("Invalid endpoint");
    if (endpoint.hostname === "localhost") endpoint.hostname = "127.0.0.1";
  } catch {
    return Response.json({ detail: "Configuración de telemetría inválida." }, { status: 503 });
  }

  const body = await request.text();
  if (new TextEncoder().encode(body).length > 819200) {
    return Response.json({ detail: "Lote de telemetría demasiado grande." }, { status: 413 });
  }
  return forwardTelemetryBatch(endpoint, body);
}