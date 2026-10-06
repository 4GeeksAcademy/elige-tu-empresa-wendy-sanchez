"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { reportRouteLoad, reportWebVital } from "../../backoffice/lib/telemetryInstrumentation";

export default function WebsiteTelemetry() {
  const pathname = usePathname();
  useReportWebVitals((metric) => reportWebVital(metric, window.location.pathname, "website"));
  useEffect(() => {
    const report = () => {
      const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
      if (navigation) reportRouteLoad(pathname, navigation.loadEventEnd || performance.now() - navigation.startTime, "website");
    };
    if (document.readyState === "complete") report();
    else window.addEventListener("load", report, { once: true });
    return () => window.removeEventListener("load", report);
  }, [pathname]);
  return null;
}