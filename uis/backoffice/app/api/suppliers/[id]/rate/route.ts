import { forwardJsonBody, proxyToSuppliersApi } from "../../../../../lib/suppliersProxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

function getForwardHeaders(request: Request): Record<string, string> {
  const auth = request.headers.get("authorization");
  return auth ? { authorization: auth } : {};
}

export async function PATCH(request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  const init = await forwardJsonBody(request);
  return proxyToSuppliersApi(
    `/${encodeURIComponent(id)}/rate`,
    { ...init, method: "PATCH" },
    { forwardHeaders: getForwardHeaders(request) },
  );
}
