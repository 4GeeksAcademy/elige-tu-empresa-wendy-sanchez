import { captureApiResult, captureResponseSignals } from "../lib/telemetryApi";
import { track } from "../lib/telemetry";
import { validTelemetryProperties } from "../lib/telemetryContracts";
import { reportLoginFailure } from "../lib/telemetryAuth";

jest.mock("../lib/telemetry", () => ({ track: jest.fn() }));
const tracked = jest.mocked(track);
afterEach(() => jest.clearAllMocks());

test("API failures are normalized and match the approved schemas", () => {
  captureApiResult("/api/inventory/products/42?email=secret", "GET", 503, 10, crypto.randomUUID());
  expect(tracked).toHaveBeenCalledTimes(2);
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
  expect(JSON.stringify(tracked.mock.calls)).not.toContain("secret");
});

test("server signals go through track with unchanged allowed properties", () => {
  const properties = { application: "backoffice", logout_reason: "user_action" };
  const response = { headers: new Headers({ "X-Telemetry-Events": JSON.stringify([{ event_type: "auth_logout_completed", properties, eventId: crypto.randomUUID(), timestamp: new Date().toISOString() }]) }) } as Response;
  captureResponseSignals(response, crypto.randomUUID());
  expect(tracked).toHaveBeenCalledWith("auth_logout_completed", properties);
});

test("versioned auth failures use approved reasons without credentials", () => {
  for (const reason of ["invalid_credentials", "session_expired", "network_error"] as const) reportLoginFailure(reason);
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
});