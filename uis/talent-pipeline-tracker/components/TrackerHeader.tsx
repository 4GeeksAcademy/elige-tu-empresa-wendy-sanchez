"use client";

import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";

export default function TrackerHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-sm font-semibold text-slate-900 hover:text-sky-700">
            Talent Pipeline Tracker
          </Link>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <Link
                href="/account/profile"
                className="text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                Mi cuenta
              </Link>
              <button
                type="button"
                onClick={logout}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                Cerrar sesión
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                Iniciar sesión
              </Link>
              <Link
                href="/register"
                className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-800"
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