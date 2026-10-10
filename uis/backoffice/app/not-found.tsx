"use client";
import { useEffect } from "react";
import Link from "next/link";
import { reportNavigationError } from "@/lib/telemetryInstrumentation";

export default function NotFound() {
  useEffect(() => reportNavigationError(window.location.pathname, "not_found"), []);
  return <main className="mx-auto max-w-3xl px-4 py-12"><h1 className="text-2xl font-semibold">Página no encontrada</h1><Link href="/" className="mt-4 inline-block text-cyan-700 underline">Volver al dashboard</Link></main>;
}