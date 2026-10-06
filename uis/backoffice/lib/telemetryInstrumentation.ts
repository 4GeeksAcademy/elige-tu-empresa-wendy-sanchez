import { track } from "./telemetry";

export const APP_VERSION = "0.1.0";
const routes = new Set([
  "/", "/login", "/register", "/forgot-password", "/reset-password",
  "/suppliers", "/inventory/products", "/inventory/orders",
  "/inventory/orders/inbound", "/inventory/orders/outbound", "/incidents",
  "/incidents/list", "/incidents/register", "/incidents/summary",
  "/incidents-manager", "/account/profile", "/account/change-password",
]);

export function telemetryRoute(path: string): string {
  try {
    const pathname = new URL(path, "http://localhost").pathname;
    if (routes.has(pathname)) return pathname;
    if (/^\/inventory\/products\/\d+$/.test(pathname)) return "/inventory/products/{id}";
    return "/other";
  } catch {
    return "/other";
  }
}

export function reportPageView(path: string, role?: string): void {
  const route = telemetryRoute(path);
  const section = route === "/" ? "dashboard"
    : route.startsWith("/inventory") ? "inventory"
    : route.startsWith("/suppliers") ? "suppliers"
    : route.startsWith("/incidents") ? "incidents"
    : route.startsWith("/account") ? "account" : "other";
  track("backoffice_page_viewed", {
    application: "backoffice", route_template: route, section, country: "unknown",
    role_group: role === "admin" ? "admin" : role === "user" ? "staff" : "unknown",
  });
}

export function reportWebVital(metric: { name: string; value: number; rating: string }, path: string): void {
  if (!["LCP", "INP", "CLS", "TTFB"].includes(metric.name) || !Number.isFinite(metric.value)) return;
  track("client_performance_recorded", {
    application: "backoffice", route_template: telemetryRoute(path), metric_name: metric.name,
    metric_value: Math.max(0, Math.min(120000, metric.value)),
    metric_rating: metric.rating === "needs-improvement" ? "needs_improvement" : metric.rating,
    app_version: APP_VERSION,
  });
}

export function installFrontendErrorCapture(): () => void {
  const signatures = new Map<string, number>();
  let windowStart = Date.now();
  let count = 0;
  const capture = (code: string) => {
    const now = Date.now();
    if (now - windowStart >= 60000) { windowStart = now; count = 0; signatures.clear(); }
    const route = telemetryRoute(window.location.pathname);
    const signature = `${code}:${route}`;
    if (count >= 20 || now - (signatures.get(signature) ?? -Infinity) < 60000) return;
    signatures.set(signature, now);
    count += 1;
    track("frontend_error_captured", {
      application: "backoffice", app_version: APP_VERSION, route_template: route,
      component: "window", error_code: code, error_class: "unknown",
    });
  };
  const onError = () => capture("uncaught_error");
  const onRejection = () => capture("unhandled_rejection");
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}