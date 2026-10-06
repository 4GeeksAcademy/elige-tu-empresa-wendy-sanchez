const ENDPOINT = "http://localhost:8000/telemetry/events";
const properties = { application: "backoffice", logout_reason: "user_action" };
const pseudonym = "a".repeat(64);

describe("telemetry capture and delivery", () => {
  let track: typeof import("../lib/telemetry").track;
  let session: typeof import("../lib/telemetrySession");
  const fetchMock = jest.fn();
  const beaconMock = jest.fn();
  let documentListener: jest.SpyInstance;
  let windowListener: jest.SpyInstance;
  const oldEndpoint = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;

  beforeEach(async () => {
    jest.resetModules();
    jest.useFakeTimers();
    process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = ENDPOINT;
    fetchMock.mockReset().mockResolvedValue({ ok: true });
    beaconMock.mockReset().mockReturnValue(true);
    global.fetch = fetchMock;
    Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: beaconMock });
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    documentListener = jest.spyOn(document, "addEventListener");
    windowListener = jest.spyOn(window, "addEventListener");
    session = await import("../lib/telemetrySession");
    session.beginTelemetrySession(pseudonym, true);
    track = (await import("../lib/telemetry")).track;
  });

  afterEach(() => {
    for (const [name, listener] of documentListener.mock.calls) document.removeEventListener(name, listener);
    for (const [name, listener] of windowListener.mock.calls) window.removeEventListener(name, listener);
    jest.restoreAllMocks();
    jest.clearAllTimers();
    jest.useRealTimers();
    if (oldEndpoint === undefined) delete process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
    else process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT = oldEndpoint;
  });

  test("captures immutable envelopes and batches exactly at ten seconds", async () => {
    const captured = new Date().toISOString();
    const payload = { ...properties };
    track("auth_logout_completed", payload);
    payload.logout_reason = "invalid";
    await jest.advanceTimersByTimeAsync(5000);
    track("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(4999);
    expect(fetchMock).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(1);
    const events = JSON.parse(fetchMock.mock.calls[0][1].body).events;
    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ timestamp: captured, userId: pseudonym, schemaVersion: "1.0.0", properties });
    expect(events[0].eventId).not.toBe(events[1].eventId);
    expect(events[0].sessionId).toBe(events[1].sessionId);
    expect(events[0].requestId).toMatch(/^[a-f0-9-]{36}$/);
    expect(fetchMock.mock.calls[0][1].credentials).toBe("same-origin");
  });

  test("flushes twenty events in one request, not one request per event", () => {
    for (let index = 0; index < 20; index++) track("auth_logout_completed", properties);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).events).toHaveLength(20);
  });

  test("retries three times at one, two and four seconds then discards", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    track("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await jest.advanceTimersByTimeAsync(2000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await jest.advanceTimersByTimeAsync(4000);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0][1].body).toBe(fetchMock.mock.calls[3][1].body);
    await jest.advanceTimersByTimeAsync(20000);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  test("visibility hidden flushes with beacon and retains refused batches", () => {
    track("auth_logout_completed", properties);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(beaconMock).not.toHaveBeenCalled();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    beaconMock.mockReturnValueOnce(false);
    document.dispatchEvent(new Event("visibilitychange"));
    document.dispatchEvent(new Event("visibilitychange"));
    expect(beaconMock).toHaveBeenCalledTimes(2);
    expect(beaconMock.mock.calls[0][0]).toBe("/api/telemetry/events");
    expect(beaconMock.mock.calls[0][1].type).toBe("application/json");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(beaconMock).toHaveBeenCalledTimes(2);
  });

  test("rejects unknown properties and invalid types without throwing or logging", async () => {
    track("unknown_event", properties);
    track("auth_logout_completed", { ...properties, email: "private@example.test" });
    track("auth_logout_completed", { ...properties, application: 7 });
    await jest.advanceTimersByTimeAsync(10000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("authenticated capture waits for pseudonym and rotates sessions on login", async () => {
    session.beginTelemetrySession(undefined, true);
    track("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(10000);
    expect(fetchMock).not.toHaveBeenCalled();
    session.beginTelemetrySession(pseudonym);
    track("auth_logout_completed", properties);
    session.beginTelemetrySession("b".repeat(64), true);
    track("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(10000);
    const events = JSON.parse(fetchMock.mock.calls[0][1].body).events;
    expect(events[0].sessionId).not.toBe(events[1].sessionId);
    expect(events[0].userId).toBe(pseudonym);
    expect(events[1].userId).toBe("b".repeat(64));
  });

  test("rejects sensitive values inside approved fields before sending", async () => {
    for (let index = 0; index < 20; index++) track("backoffice_page_viewed", {
      application: "backoffice", route_template: "/account/email-canary@example.com",
      section: "account", country: "unknown", role_group: "staff",
    });
    track("frontend_error_captured", { application: "backoffice", app_version: "0.1.0", route_template: "/", component: "JaneSmith", error_code: "uncaught_error", error_class: "unknown" });
    await jest.advanceTimersByTimeAsync(10000);
    expect(fetchMock).not.toHaveBeenCalled();
    window.dispatchEvent(new Event("pagehide"));
    expect(beaconMock).not.toHaveBeenCalled();
  });

  test("no configured endpoint disables capture", async () => {
    jest.resetModules();
    delete process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
    const disabledTrack = (await import("../lib/telemetry")).track;
    disabledTrack("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(20000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("expired restored sessions emit anonymously once without enabling normal authenticated capture", async () => {
    session.beginTelemetrySession(undefined, true);
    const { reportSessionExpired } = await import("../lib/telemetryAuth");
    reportSessionExpired();
    reportSessionExpired();
    track("auth_logout_completed", properties);
    await jest.advanceTimersByTimeAsync(10000);
    const events = JSON.parse(fetchMock.mock.calls[0][1].body).events;
    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe("auth_session_expired");
    expect(events[0].userId).toMatch(/^anonymous_/);
    expect(session.getTelemetrySession()).toBeUndefined();
  });

  test("events captured during a request stay in a separate batch", async () => {
    let finish!: (response: { ok: boolean }) => void;
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    for (let index = 0; index < 20; index++) track("auth_logout_completed", properties);
    track("auth_logout_completed", properties);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    finish({ ok: true });
    await jest.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).events).toHaveLength(1);
  });

  test("beacon covers an in-flight batch and prevents retries of a queued beacon", async () => {
    let fail!: (error: Error) => void;
    fetchMock.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
    for (let index = 0; index < 20; index++) track("auth_logout_completed", properties);
    track("auth_logout_completed", properties);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(beaconMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
    fail(new Error("aborted"));
    await jest.advanceTimersByTimeAsync(20000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("queue remains bounded during an outage", () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    for (let index = 0; index < 250; index++) track("auth_logout_completed", properties);
    window.dispatchEvent(new Event("pagehide"));
    const delivered = beaconMock.mock.calls.reduce((total, call) => total + (call[1] as Blob).size, 0);
    expect(beaconMock).toHaveBeenCalledTimes(10);
    expect(delivered).toBeGreaterThan(0);
    expect(beaconMock.mock.calls.every((call) => (call[1] as Blob).size < 48000)).toBe(true);
  });
});