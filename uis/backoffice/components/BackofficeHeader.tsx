"use client";

import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";

/**
 * Barra de navegación del backoffice. Muestra enlaces de sesión en función
 * del estado de autenticación: Mi cuenta / Cerrar sesión si hay sesión,
 * o Login / Registro si no la hay.
 */
export default function BackofficeHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-slate-200 bg-slate-950 text-slate-50">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
            Internal App
          </p>
          <h1 className="text-lg font-semibold">HealthCore Backoffice</h1>
          <nav className="mt-2 flex gap-3 text-xs text-slate-300">
            <Link className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white" href="/">
              Dashboard
            </Link>
            <Link
              className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white"
              href="/incidents"
            >
              Incident Analysis
            </Link>
            <Link
              className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white"
              href="/suppliers"
            >
              Supplier Directory
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <Link
                className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300 hover:text-white"
                href="/account/profile"
              >
                Mi cuenta
              </Link>
              <button
                type="button"
                onClick={logout}
                className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300 hover:text-white hover:border-red-400"
              >
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <Link
                className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300 hover:text-white"
                href="/login"
              >
                Iniciar sesión
              </Link>
              <Link
                className="rounded-full bg-cyan-600 px-3 py-1 text-xs font-semibold text-white hover:bg-cyan-500"
                href="/register"
              >
                Registrarse
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}