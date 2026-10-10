export async function forwardTelemetryBatch(endpoint: URL, body: string): Promise<Response> {
  try {
    const upstream = await fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" }, body,
      cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(10000),
    });
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "El receptor de telemetría no está disponible." }, { status: 502 });
  }
}