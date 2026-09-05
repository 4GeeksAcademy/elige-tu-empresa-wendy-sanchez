const BACKEND_URL = process.env.SUPPLIERS_API_URL ?? process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

export async function proxyToSuppliersApi(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let upstream: Response;

  try {
    upstream = await fetch(`${BACKEND_URL}/api/suppliers${path}`, {
      ...init,
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "No se pudo contactar con la API de proveedores. ¿Está levantada en el puerto 8000?" },
      { status: 502 },
    );
  }

  if (upstream.status === 204) {
    return new Response(null, { status: 204 });
  }

  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
}

export async function forwardJsonBody(request: Request): Promise<RequestInit> {
  const payload = await request.text();
  return {
    body: payload,
    headers: { "content-type": "application/json" },
  };
}
