"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { useAuth } from "@/lib/AuthContext";
import { installFrontendErrorCapture, reportPageView, reportRouteLoad, reportWebVital } from "@/lib/telemetryInstrumentation";

export default function TelemetryObserver() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const previousRoute = useRef<string | undefined>(undefined);
  useReportWebVitals((metric) => reportWebVital(metric, window.location.pathname));

  useEffect(() => installFrontendErrorCapture(), []);
  useEffect(() => {
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (navigation) reportRouteLoad(pathname, navigation.loadEventEnd || performance.now() - navigation.startTime, "backoffice");
  }, []);
  useEffect(() => {
    if (loading || previousRoute.current === pathname) return;
    const timer = setTimeout(() => {
      reportPageView(pathname, user?.role);
      previousRoute.current = pathname;
    }, 500);
    return () => clearTimeout(timer);
  }, [pathname, loading, user?.role]);
  return null;
}