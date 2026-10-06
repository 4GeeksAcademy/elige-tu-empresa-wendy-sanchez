import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { useInventoryTelemetry } from "../lib/useInventoryTelemetry";
import { track } from "../lib/telemetry";
import { validTelemetryProperties } from "../lib/telemetryContracts";

jest.mock("../lib/telemetry", () => ({ track: jest.fn() }));
const tracked = jest.mocked(track);

test("a real started workflow emits abandonment on unmount without form values", async () => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  function Harness() { useInventoryTelemetry("inbound", "1", null); return null; }
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () => root.render(createElement(Harness)));
  await act(async () => root.unmount());
  expect(tracked.mock.calls.map(([name]) => name)).toEqual(["inventory_workflow_started", "inventory_workflow_abandoned"]);
  for (const [name, properties] of tracked.mock.calls) expect(validTelemetryProperties(name, properties)).toBe(true);
});