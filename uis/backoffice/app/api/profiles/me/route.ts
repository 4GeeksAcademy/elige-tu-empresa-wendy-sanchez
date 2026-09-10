import { forwardAuthorizedJsonBody, proxyToAuthApi } from "@/lib/authProxy";

export async function GET(request: Request): Promise<Response> {
  const auth = request.headers.get("authorization");
  return proxyToAuthApi("/profiles/me", {
    method: "GET",
    headers: { ...(auth ? { authorization: auth } : {}) },
  });
}

export async function PUT(request: Request): Promise<Response> {
  const init = await forwardAuthorizedJsonBody(request);
  return proxyToAuthApi("/profiles/me", { ...init, method: "PUT" });
}