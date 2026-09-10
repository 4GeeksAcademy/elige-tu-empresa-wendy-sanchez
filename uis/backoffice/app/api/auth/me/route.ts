import { forwardAuthorizationHeader, proxyToAuthApi } from "@/lib/authProxy";

export async function GET(request: Request): Promise<Response> {
  const auth = await forwardAuthorizationHeader(request);
  return proxyToAuthApi("/auth/me", { ...auth, method: "GET" });
}