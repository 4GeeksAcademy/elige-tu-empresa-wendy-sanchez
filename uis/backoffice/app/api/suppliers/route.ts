import { forwardJsonBody, proxyToSuppliersApi } from "../../../lib/suppliersProxy";

function getForwardHeaders(request: Request): Record<string, string> {
  const auth = request.headers.get("authorization");
  return auth ? { authorization: auth } : {};
}

export async function GET(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  const params = new URLSearchParams();

  const country = incoming.searchParams.get("country");
  const category = incoming.searchParams.get("category");
  if (country) params.set("country", country);
  if (category) params.set("category", category);

  const query = params.toString();
  return proxyToSuppliersApi(query ? `?${query}` : "", {}, { forwardHeaders: getForwardHeaders(request) });
}

export async function POST(request: Request): Promise<Response> {
  const init = await forwardJsonBody(request);
  return proxyToSuppliersApi("", { ...init, method: "POST" }, { forwardHeaders: getForwardHeaders(request) });
}
