/** Parámetros adicionales que el proxy puede recibir del route handler. */
interface ProxyOptions {
  /**
   * Cabeceras que el route handler recibe del navegador y que deben reenviarse
   * al backend. Especialmente útil para `authorization: Bearer <token>`.
   */
  forwardHeaders?: Record<string, string>;
}

const BACKEND_URL = process.env.SUPPLIERS_API_URL ?? process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

export async function proxyToSuppliersApi(
  path: string,
  init: RequestInit = {},
  options?: ProxyOptions,
): Promise<Response> {
  let upstream: Response;

  const mergedHeaders: Record<string, string> = {
    ...(init.headers as Record<string, string> ?? {}),
    ...(options?.forwardHeaders ?? {}),
  };

  try {
    upstream = await fetch(`${BACKEND_URL}/api/suppliers${path}`, {
      ...init,
      headers: mergedHeaders,
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
