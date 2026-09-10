"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";

/**
 * Página de restablecimiento de contraseña (paso 1: solicitar enlace).
 *
 * - Siempre muestra el mismo mensaje de confirmación (independientemente de
 *   si el email existe) para evitar la enumeración de usuarios.
 * - Desactiva el formulario tras el envío para evitar peticiones duplicadas.
 */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function validate(): string | null {
    if (!email.trim()) return "El email es obligatorio";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      return "Introduce un email válido";
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }

    try {
      setSubmitting(true);
      // El backend devuelve siempre 200 sea cual sea el resultado, de modo
      // que el formulario muestra el mismo mensaje de confirmación.
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      if (!response.ok) {
        const data = (await response.json()) as { detail?: unknown };
        const msg =
          typeof data.detail === "string" ? data.detail : "Error al enviar la solicitud";
        setError(msg);
        return;
      }

      setSubmitted(true);
    } catch {
      setError("No se pudo conectar con el servidor. Inténtalo de nuevo.");
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
        <h1 className="mt-2 text-2xl font-bold text-slate-900">¿Olvidaste tu contraseña?</h1>
        <p className="mt-1 text-sm text-slate-600">
          Introduce tu email y te enviaremos un enlace para restablecerla.
        </p>

        {submitted ? (
          <div className="mt-6 rounded-lg border border-green-200 bg-green-50 px-4 py-4 text-sm text-green-800">
            <p className="font-medium">Solicitud recibida</p>
            <p className="mt-1">
              Si esa dirección está registrada, recibirás un enlace para restablecer tu
              contraseña en breve.
            </p>
            <p className="mt-3">
              <Link href="/login" className="font-semibold text-cyan-700 hover:text-cyan-800">
                Volver a iniciar sesión
              </Link>
            </p>
          </div>
        ) : (
          <>
            {error && (
              <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                {error}
              </div>
            )}

            <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
              <label className="grid gap-1">
                <span className="text-sm font-medium text-slate-700">Email</span>
                <input
                  type="email"
                  className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError(null);
                  }}
                  placeholder="usuario@healthcore.com"
                  autoComplete="email"
                  disabled={submitting}
                  required
                />
                {error && <span className="text-sm text-red-700">{error}</span>}
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
              >
                {submitting ? "Enviando..." : "Enviar enlace de restablecimiento"}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-600">
              <Link href="/login" className="font-semibold text-cyan-700 hover:text-cyan-800">
                Volver a iniciar sesión
              </Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}