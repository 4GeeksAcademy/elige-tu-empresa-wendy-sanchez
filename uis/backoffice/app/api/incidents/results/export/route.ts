const BACKEND_URL = process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

export async function GET(): Promise<Response> {
  const upstream = await fetch(`${BACKEND_URL}/api/incidents/results/export`, {
    method: "GET",
    cache: "no-store",
  });

  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "text/csv; charset=utf-8",
      "content-disposition":
        upstream.headers.get("content-disposition") ?? "attachment; filename=results.csv",
    },
  });
}
