import { forwardTelemetryBatch } from "../../../../lib/TelemetryService.server";

export async function POST(request: Request): Promise<Response> {
  try {
    const primary = process.env.TELEMETRY_ENDPOINT ?? process.env.SUPPLIERS_API_URL ?? "http://127.0.0.1:8000";
    const endpoint = new URL(process.env.TELEMETRY_CONTROL_ENDPOINT ?? "/telemetry/control", primary);
    const body = await request.text();
    if (body.length > 819200) return Response.json({ detail: "Batch too large" }, { status: 413 });
    return forwardTelemetryBatch(endpoint, body);
  } catch { return Response.json({ detail: "Control unavailable" }, { status: 502 }); }
}