"use client";

import { type FormEvent, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";

interface FieldErrors {
  email?: string;
  password?: string;
  general?: string;
}

/**
 * Envuelto en <Suspense> porque usa useSearchParams() (requerido por Next.js
 * para que no se rompa el prerenderizado estático de la página).
 */
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12">
          <p className="text-sm text-slate-500">Cargando...</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const searchParams = useSearchParams();
  const resetOk = searchParams.get("reset") === "ok";

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
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const data = (await response.json()) as { access_token?: string; detail?: string | unknown };

      if (!response.ok) {
        // Mostrar el mensaje de error real que devuelve la API
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : "Email o contraseña incorrectos.";
        setErrors({ general: msg });
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
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">
          HealthCore
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Iniciar sesión</h1>
        <p className="mt-1 text-sm text-slate-600">
          Accede al panel de operaciones internas de HealthCore.
        </p>

        {resetOk && (
          <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            Contraseña restablecida correctamente. Inicia sesión con tu nueva contraseña.
          </div>
        )}

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
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="usuario@healthcore.com"
              required
            />
            {errors.email && (
              <span className="text-sm text-red-700">{errors.email}</span>
            )}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
            />
            {errors.password && (
              <span className="text-sm text-red-700">{errors.password}</span>
            )}
            <span className="text-right">
              <Link
                href="/forgot-password"
                className="text-sm font-medium text-cyan-700 hover:text-cyan-800"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </span>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
          >
            {submitting ? "Iniciando sesión..." : "Iniciar sesión"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          ¿No tienes cuenta?{" "}
          <Link href="/register" className="font-semibold text-cyan-700 hover:text-cyan-800">
            Regístrate aquí
          </Link>
        </p>
      </div>
    </main>
  );
}