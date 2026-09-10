import { forwardJsonBody, proxyToAuthApi } from "@/lib/authProxy";

export async function POST(request: Request): Promise<Response> {
  const init = await forwardJsonBody(request);
  return proxyToAuthApi("/users", { ...init, method: "POST" });
}