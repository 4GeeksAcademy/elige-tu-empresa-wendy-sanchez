import { forwardAuthorizedJsonBody, proxyToAuthApi } from "@/lib/authProxy";

export async function POST(request: Request): Promise<Response> {
  const init = await forwardAuthorizedJsonBody(request);
  return proxyToAuthApi("/auth/change-password", { ...init, method: "POST" });
}