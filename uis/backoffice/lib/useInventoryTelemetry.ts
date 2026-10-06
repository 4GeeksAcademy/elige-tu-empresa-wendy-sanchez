"use client";

import { useEffect, useRef } from "react";
import { track } from "./telemetry";

export function useInventoryTelemetry(operation: "inbound" | "outbound", clinicId: string, success: string | null) {
  const clinic = Number(clinicId);
  const activeClinic = useRef<number | undefined>(undefined);
  const startedClinic = useRef(0);
  const flow = useRef<{ started?: number; clinic?: number; completed: boolean; closed: boolean; blocked: boolean }>({ completed: false, closed: false, blocked: false });
  useEffect(() => {
    if (!Number.isInteger(clinic) || clinic < 1 || clinic > 12) { startedClinic.current = 0; return; }
    activeClinic.current = clinic;
    if (!flow.current.started || flow.current.completed) flow.current = { started: Date.now(), clinic, completed: false, closed: false, blocked: false };
    flow.current.clinic = clinic;
    if (startedClinic.current === clinic) return;
    startedClinic.current = clinic;
    track("inventory_workflow_started", {
      operation, clinic_id: clinic, country: clinic <= 9 ? "US" : "UK", entry_surface: `${operation}_form`,
    });
  }, [clinic, operation]);
  useEffect(() => {
    if (success && activeClinic.current) {
      flow.current.completed = true;
      track("inventory_order_confirmation_viewed", {
      operation, clinic_id: activeClinic.current, country: activeClinic.current <= 9 ? "US" : "UK", result: "success",
      });
    }
  }, [success, operation]);
  useEffect(() => {
    const abandon = () => {
      const state = flow.current;
      if (!state.started || !state.clinic || state.completed || state.closed) return;
      state.closed = true;
      track("inventory_workflow_abandoned", { operation, clinic_id: state.clinic, country: state.clinic <= 9 ? "US" : "UK",
        last_step: state.blocked ? "validate" : "select_clinic", abandonment_reason: state.blocked ? "validation_blocked" : "navigation_away",
        elapsed_seconds: Math.min(86400, Math.round((Date.now() - state.started) / 1000)) });
    };
    window.addEventListener("pagehide", abandon);
    return () => { window.removeEventListener("pagehide", abandon); abandon(); };
  }, [operation]);
  return (field: string, code: string) => {
    flow.current.blocked = true;
    if (Number.isInteger(clinic) && clinic >= 1 && clinic <= 12) track("inventory_form_validation_failed", {
      operation, clinic_id: clinic, country: clinic <= 9 ? "US" : "UK", field_name: field, validation_code: code,
    });
  };
}