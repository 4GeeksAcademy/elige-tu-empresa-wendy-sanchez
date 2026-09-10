import { proxyToSuppliersApi } from "../../../../lib/suppliersProxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

function getForwardHeaders(request: Request): Record<string, string> {
  const auth = request.headers.get("authorization");
  return auth ? { authorization: auth } : {};
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  return proxyToSuppliersApi(`/${encodeURIComponent(id)}`, {}, { forwardHeaders: getForwardHeaders(request) });
}

export async function DELETE(request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  return proxyToSuppliersApi(`/${encodeURIComponent(id)}`, { method: "DELETE" }, { forwardHeaders: getForwardHeaders(request) });
}
