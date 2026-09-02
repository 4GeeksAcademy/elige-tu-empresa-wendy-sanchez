const BACKEND_URL = process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request): Promise<Response> {
  const incomingForm = await request.formData();
  const incomingFile = incomingForm.get("file");

  if (!(incomingFile instanceof File)) {
    return Response.json(
      { detail: "Debes enviar un fichero CSV" },
      { status: 400 },
    );
  }

  const outgoingForm = new FormData();
  outgoingForm.append("file", incomingFile, incomingFile.name || "incidents.csv");

  const upstream = await fetch(`${BACKEND_URL}/api/incidents/analyze`, {
    method: "POST",
    body: outgoingForm,
    cache: "no-store",
  });

  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
}
