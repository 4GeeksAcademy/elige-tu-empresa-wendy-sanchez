import { proxyToSuppliersApi } from "../../../../lib/suppliersProxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(_request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  return proxyToSuppliersApi(`/${encodeURIComponent(id)}`);
}

export async function DELETE(_request: Request, context: RouteContext): Promise<Response> {
  const { id } = await context.params;
  return proxyToSuppliersApi(`/${encodeURIComponent(id)}`, { method: "DELETE" });
}
