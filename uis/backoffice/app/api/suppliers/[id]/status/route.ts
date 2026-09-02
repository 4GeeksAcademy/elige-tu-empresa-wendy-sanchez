import { forwardJsonBody, proxyToSuppliersApi } from "../../../../../lib/suppliersProxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function PATCH(request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  const init = await forwardJsonBody(request);
  return proxyToSuppliersApi(`/${encodeURIComponent(id)}/status`, { ...init, method: "PATCH" });
}
