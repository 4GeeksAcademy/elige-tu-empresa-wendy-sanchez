import { track } from "../lib/telemetry";
import { validTelemetryProperties } from "../lib/telemetryContracts";
import { installFrontendErrorCapture, reportInventoryFilter, reportInventorySearch, reportNavigationError, reportPageView, reportRouteLoad, reportWebVital, telemetryRoute } from "../lib/telemetryInstrumentation";

jest.mock("../lib/telemetry", () => ({ track: jest.fn() }));
const tracked = jest.mocked(track);

afterEach(() => jest.clearAllMocks());

test("diagnostic event references reject names outside the registry", () => {
  const properties = { producer: "backoffice", event_type: "inbound_order_created", drop_reason: "privacy_rejected", schema_version: "1.0.0", count_bucket: "1" };
  expect(validTelemetryProperties("telemetry_event_dropped", properties)).toBe(true);
  expect(validTelemetryProperties("telemetry_event_dropped", { ...properties, event_type: "jane_smith" })).toBe(false);
});

test("normalizes routes and excludes user input and query strings", () => {
  expect(telemetryRoute("/inventory/products/42?email=secret@example.test")).toBe("/inventory/products/{id}");
  expect(telemetryRoute("/private/secret@example.test")).toBe("/other");
  for (const path of ["/", "/inventory/products", "/suppliers", "/incidents", "/account/profile"]) reportPageView(path);
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
});

test("reports approved vitals with route and normalized rating", () => {
  reportWebVital({ name: "LCP", value: 3000, rating: "needs-improvement" }, "/suppliers?email=secret");
  reportWebVital({ name: "FCP", value: 1000, rating: "good" }, "/");
  expect(tracked).toHaveBeenCalledTimes(1);
  const [name, properties] = tracked.mock.calls[0];
  expect(properties).toMatchObject({ route_template: "/suppliers", metric_rating: "needs_improvement" });
  expect(validTelemetryProperties(name, properties)).toBe(true);
});

test("website vitals keep the real application and public routes", () => {
  reportWebVital({ name: "LCP", value: 2500, rating: "good" }, "/es", "website");
  const [name, properties] = tracked.mock.calls[0];
  expect(properties).toMatchObject({ application: "website", route_template: "/es" });
  expect(validTelemetryProperties(name, properties)).toBe(true);
});

test("filters, search, route loading and navigation failures keep their allowlists", () => {
  reportInventoryFilter("medications", 8);
  reportInventorySearch(3, 8);
  reportNavigationError("/private/email-canary@example.com", "not_found");
  reportRouteLoad("/es", 100, "website");
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
  expect(JSON.stringify(tracked.mock.calls)).not.toContain("email-canary");
});

test("captures global errors without messages or stacks, deduplicates and cleans up", () => {
  const cleanup = installFrontendErrorCapture();
  window.dispatchEvent(new ErrorEvent("error", { message: "password=private", error: new Error("secret") }));
  window.dispatchEvent(new ErrorEvent("error", { message: "other secret" }));
  window.dispatchEvent(new Event("unhandledrejection"));
  expect(tracked).toHaveBeenCalledTimes(2);
  expect(JSON.stringify(tracked.mock.calls)).not.toMatch(/password|private|secret/);
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
  cleanup();
  window.dispatchEvent(new Event("unhandledrejection"));
  expect(tracked).toHaveBeenCalledTimes(2);
});