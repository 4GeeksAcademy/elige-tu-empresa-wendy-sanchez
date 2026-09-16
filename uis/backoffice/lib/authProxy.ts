/** Proxy client-side hacia la API de autenticación de HealthCore. */

const BACKEND_URL = process.env.SUPPLIERS_API_URL ?? process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

/**
 * Reenvía una petición al backend FastAPI conservando el body JSON y,
 * opcionalmente, la cabecera Authorization del cliente (para rutas protegidas).
 */
export async function proxyToAuthApi(path: string, init: RequestInit = {}): Promise<Response> {
  let upstream: Response;

  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "No se pudo contactar con la API de autenticación. Inténtalo de nuevo más tarde." },
      { status: 502 },
    );
  }

  if (upstream.status === 204) {
    return new Response(null, { status: 204 });
  }

  try {
    const body = await upstream.arrayBuffer();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      { detail: "Error al leer la respuesta del servidor de autenticación." },
      { status: 502 },
    );
  }
}

/** Extrae el body JSON entrante manteniendo la cabecera de contenido. */
export async function forwardJsonBody(request: Request): Promise<RequestInit> {
  const payload = await request.text();
  return {
    body: payload,
    headers: { "content-type": "application/json" },
  };
}

/**
 * Reenvía la cabecera Authorization (`Authorization: Bearer <token>`) que el
 * navegador incluyó en la petición al proxie. El token nunca se lee en el
 * servidor: se pasa tal cual al backend para que lo valide.
 */
export async function forwardAuthorizationHeader(request: Request): Promise<RequestInit> {
  const incoming = request.headers.get("authorization");
  if (!incoming) return {};
  return { headers: { authorization: incoming } };
}

/** Combina el body entrante con la cabecera Authorization del cliente. */
export async function forwardAuthorizedJsonBody(request: Request): Promise<RequestInit> {
  const [json, auth] = await Promise.all([forwardJsonBody(request), forwardAuthorizationHeader(request)]);
  return {
    ...json,
    headers: {
      ...(json.headers ?? {}),
      ...(auth.headers ?? {}),
    },
  };
}