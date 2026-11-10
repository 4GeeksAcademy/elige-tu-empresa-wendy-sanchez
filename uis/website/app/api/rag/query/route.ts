/**
 * Next.js API route that proxies /api/rag/query to the FastAPI RAG backend.
 *
 * This route is used when the frontend and backend are on the same origin
 * (e.g., Vercel/Netlify deployment).  For local development the RagChat
 * component calls the FastAPI server directly at localhost:8000.
 *
 * The RAG backend URL is configured via the RAG_API_BASE env var (default
 * http://localhost:8000).
 */

export const runtime = "edge";

export async function POST(request: Request): Promise<Response> {
  const apiBase = process.env.RAG_API_BASE ?? "http://localhost:8000";

  try {
    const body = await request.json();
    const upstream = await fetch(`${apiBase}/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!upstream.ok) {
      return Response.json(
        { error: "Upstream RAG API error", status: upstream.status },
        { status: upstream.status },
      );
    }
    const data = await upstream.json();
    return Response.json(data);
  } catch (err) {
    return Response.json(
      { error: "Failed to reach RAG API", detail: String(err) },
      { status: 502 },
    );
  }
}