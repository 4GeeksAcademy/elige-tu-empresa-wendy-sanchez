/**
 * Tests for lib/suppliersProxy.ts — API proxy helpers for Next.js route handlers.
 *
 * Usamos node porque estas funciones corren en server-side (Next.js API Routes)
 * donde Response y fetch están disponibles nativamente.
 *
 * @jest-environment node
 */

/// <reference types="jest" />
/// <reference types="node" />

import { forwardJsonBody, proxyToSuppliersApi } from "../lib/suppliersProxy";

// ---------------------------------------------------------------------------
//  Mock global fetch
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

function mockFetchResponse(body: unknown, status = 200, headers?: HeadersInit): Response {
  if (status === 204) {
    return new Response(null, { status: 204 });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: headers ?? { "content-type": "application/json" },
  });
}

beforeEach(() => {
  jest.resetAllMocks();
});

afterEach(() => {
  delete process.env.SUPPLIERS_API_URL;
  delete process.env.INCIDENTS_API_URL;
});

// ---------------------------------------------------------------------------
//  proxyToSuppliersApi
// ---------------------------------------------------------------------------

describe("proxyToSuppliersApi()", () => {
  it("happy path: reenvía a backend y retorna Response con body", async () => {
    mockFetch.mockResolvedValueOnce(mockFetchResponse({ id: 1, name: "Test" }));

    const result = await proxyToSuppliersApi("/1", { method: "GET" });

    expect(result.status).toBe(200);
    const body = await result.json();
    expect(body).toEqual({ id: 1, name: "Test" });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://backend:8000/api/suppliers/1");
    expect(init.method).toBe("GET");
    expect((init as RequestInit).cache).toBe("no-store");
  });

  it("happy path: reenvía cabeceras forwardHeaders", async () => {
    mockFetch.mockResolvedValueOnce(mockFetchResponse({}));

    await proxyToSuppliersApi("/rate", {}, { forwardHeaders: { authorization: "Bearer xxx" } });

    const [, init] = mockFetch.mock.calls[0];
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer xxx");
  });

  it("happy path: usa SUPPLIERS_API_URL del entorno", async () => {
    process.env.SUPPLIERS_API_URL = "https://api.example.com";
    jest.resetModules();
    mockFetch.mockResolvedValueOnce(mockFetchResponse({}));

    const { proxyToSuppliersApi: proxy } = await import("../lib/suppliersProxy");
    await proxy("/list", { method: "GET" });

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/suppliers/list");
  });

  it("usa INCIDENTS_API_URL si SUPPLIERS_API_URL no está definido", async () => {
    process.env.INCIDENTS_API_URL = "http://incidents-api:8080";
    jest.resetModules();
    mockFetch.mockResolvedValueOnce(mockFetchResponse({}));

    const { proxyToSuppliersApi: proxy } = await import("../lib/suppliersProxy");
    await proxy("/status");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe("http://incidents-api:8080/api/suppliers/status");
  });

  it("failure mode: backend caído retorna 502", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("fetch failed"));

    const result = await proxyToSuppliersApi("/1", { method: "GET" });

    expect(result.status).toBe(502);
    const body = await result.json();
    expect(body.detail).toContain("No se pudo contactar");
  });

  it("failure mode: error al leer body retorna 502", async () => {
    const badResponse = new Response("", { status: 200 });
    jest.spyOn(badResponse, "arrayBuffer").mockRejectedValueOnce(new Error("Buffer error"));
    mockFetch.mockResolvedValueOnce(badResponse);

    const result = await proxyToSuppliersApi("/1");

    expect(result.status).toBe(502);
    const body = await result.json();
    expect(body.detail).toContain("Error al leer la respuesta");
  });

  it("edge: backend retorna 204 → Response vacío con 204", async () => {
    mockFetch.mockResolvedValueOnce(mockFetchResponse(null, 204));

    const result = await proxyToSuppliersApi("/1", { method: "DELETE" });

    expect(result.status).toBe(204);
  });

  it("edge: mergea init.headers con forwardHeaders (forwardHeaders gana)", async () => {
    mockFetch.mockResolvedValueOnce(mockFetchResponse({}));

    await proxyToSuppliersApi(
      "/1",
      { headers: { "x-custom": "value" } as Record<string, string> },
      { forwardHeaders: { authorization: "Bearer token" } },
    );

    const [, init] = mockFetch.mock.calls[0];
    const headers = init.headers as Record<string, string>;
    expect(headers["x-custom"]).toBe("value");
    expect(headers["authorization"]).toBe("Bearer token");
  });
});

// ---------------------------------------------------------------------------
//  forwardJsonBody
// ---------------------------------------------------------------------------

describe("forwardJsonBody()", () => {
  it("happy path: extrae body y retorna init con content-type", async () => {
    const request = {
      text: () => Promise.resolve('{"name": "Test Supplier"}'),
    } as Request;

    const init = await forwardJsonBody(request);

    expect(init.body).toBe('{"name": "Test Supplier"}');
    expect(init.headers).toEqual({ "content-type": "application/json" });
  });

  it("failure mode: request sin body retorna cadena vacía", async () => {
    const request = {
      text: () => Promise.resolve(""),
    } as Request;

    const init = await forwardJsonBody(request);

    expect(init.body).toBe("");
    expect(init.headers).toEqual({ "content-type": "application/json" });
  });

  it("failure mode: error al leer request.text lanza excepción", async () => {
    const request = {
      text: () => Promise.reject(new Error("Stream error")),
    } as Request;

    await expect(forwardJsonBody(request)).rejects.toThrow("Stream error");
  });
});