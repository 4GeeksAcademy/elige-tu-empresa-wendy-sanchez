/** @jest-environment node */

import { POST } from "../app/api/telemetry/events/route";
import { browserTelemetryEndpoint } from "../lib/telemetryEndpoint";

const originalEnvironment = { ...process.env };
afterEach(() => { process.env = { ...originalEnvironment }; jest.restoreAllMocks(); });

test("loopback endpoints use same origin; external collectors keep their configured URL", () => {
  for (const endpoint of ["http://localhost:8000/telemetry/events", "http://127.0.0.1:8000/telemetry/events", "http://[::1]:8000/telemetry/events"]) {
    expect(browserTelemetryEndpoint(endpoint)).toBe("/api/telemetry/events");
  }
  expect(browserTelemetryEndpoint("https://collector.example.com/events")).toBe("https://collector.example.com/events");
  expect(browserTelemetryEndpoint("/api/telemetry/events")).toBe("/api/telemetry/events");
  expect(browserTelemetryEndpoint(undefined)).toBeUndefined();
  expect(browserTelemetryEndpoint("not-a-url")).toBeUndefined();
});

test("proxy forwards the whole batch, not cookies or auth, and returns the receipt", async () => {
  delete process.env.TELEMETRY_ENDPOINT;
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = "http://localhost:8000/telemetry/events";
  const body = JSON.stringify({ events: [{ event_type: "first" }, { event_type: "second" }] });
  const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue(Response.json({ received: 2 }));
  const response = await POST(new Request("https://backoffice.example.com/api/telemetry/events", {
    method: "POST", body, headers: { Authorization: "Bearer private", Cookie: "private=value" },
  }));
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ received: 2 });
  expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:8000/telemetry/events");
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ body, credentials: "omit", headers: { "Content-Type": "application/json" } });
});

test("proxy preserves validation failures and contains connection errors", async () => {
  process.env.TELEMETRY_ENDPOINT = "http://127.0.0.1:8000/telemetry/events";
  const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue(Response.json({ detail: "Invalid batch" }, { status: 422 }));
  const request = () => new Request("http://localhost/api/telemetry/events", { method: "POST", body: '{"events":[]}' });
  expect((await POST(request())).status).toBe(422);
  fetchMock.mockRejectedValue(new TypeError("connection refused"));
  expect((await POST(request())).status).toBe(502);
});

test("Docker uses the internal backend, while an explicit server collector takes precedence", async () => {
  delete process.env.TELEMETRY_ENDPOINT;
  process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = "http://localhost:8000/telemetry/events";
  process.env.SUPPLIERS_API_URL = "http://backend:8000";
  const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue(Response.json({ received: 1 }));
  const request = () => new Request("http://localhost/api/telemetry/events", { method: "POST", body: '{"events":[{}]}' });
  await POST(request());
  expect(String(fetchMock.mock.calls[0][0])).toBe("http://backend:8000/telemetry/events");
  process.env.TELEMETRY_ENDPOINT = "https://collector.example.com/events";
  fetchMock.mockResolvedValue(Response.json({ received: 1 }));
  await POST(request());
  expect(String(fetchMock.mock.calls[1][0])).toBe("https://collector.example.com/events");
});