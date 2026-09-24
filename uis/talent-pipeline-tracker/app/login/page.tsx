"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface FieldErrors {
  email?: string;
  password?: string;
  general?: string;
}

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): FieldErrors {
    const errs: FieldErrors = {};
    if (!email.trim()) errs.email = "El email es obligatorio";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      errs.email = "Introduce un email válido";
    if (!password) errs.password = "La contraseña es obligatoria";
    return errs;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});

    const validation = validate();
    if (Object.keys(validation).length > 0) {
      setErrors(validation);
      return;
    }

    try {
      setSubmitting(true);
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const data = (await response.json()) as { access_token?: string; detail?: string };

      if (!response.ok) {
        setErrors({ general: data.detail ?? "Error al iniciar sesión" });
        return;
      }

      if (data.access_token) {
        login(data.access_token);
      }
    } catch {
      setErrors({ general: "No se pudo conectar con el servidor. Inténtalo de nuevo." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <div className="w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
          HealthCore
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Iniciar sesión</h1>
        <p className="mt-1 text-sm text-slate-600">
          Accede al Talent Pipeline Tracker.
        </p>

        {errors.general && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {errors.general}
          </div>
        )}

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-600 focus:ring"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="usuario@healthcore.com"
              required
            />
            {errors.email && <span className="text-sm text-red-700">{errors.email}</span>}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-600 focus:ring"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
            />
            {errors.password && <span className="text-sm text-red-700">{errors.password}</span>}
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50"
          >
            {submitting ? "Iniciando sesión..." : "Iniciar sesión"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          ¿No tienes cuenta?{" "}
          <Link href="/register" className="font-semibold text-sky-700 hover:text-sky-800">
            Regístrate aquí
          </Link>
        </p>
      </div>
    </main>
  );
}