import { track } from "./telemetry";
import { getTelemetrySession } from "./telemetrySession";
import { telemetryRoute } from "./telemetryInstrumentation";

let expiredSession: string | undefined;
export function reportSessionExpired(): void {
  const session = getTelemetrySession();
  if (!session || expiredSession === session.sessionId) return;
  expiredSession = session.sessionId;
  track("auth_session_expired", {
    application: "backoffice", expiry_reason: "timeout", route_template: telemetryRoute(window.location.pathname),
  });
}

export function reportLoginFailure(reason: "invalid_credentials" | "session_expired" | "network_error" | "service_error", rateLimited = false): void {
  track("auth_login_failed", { application: "backoffice", failure_code: reason, auth_method: "password", rate_limited: rateLimited });
}