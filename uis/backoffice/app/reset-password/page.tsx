"use client";

import { type FormEvent, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

/**
 * Página de restablecimiento de contraseña (paso 2: establecer nueva).
 *
 * Lee el token del query string (?token=...) y lo envía a la API junto
 * con la nueva contraseña. Si tiene éxito redirige a /login con un mensaje
 * de éxito. Si falla (token expirado/inválido) muestra un error claro.
 */
export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12">
          <p className="text-sm text-slate-500">Cargando...</p>
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): string | null {
    if (!newPassword) return "La nueva contraseña es obligatoria";
    if (newPassword.length < 8) return "La contraseña debe tener al menos 8 caracteres";
    if (newPassword !== confirmPassword) return "Las contraseñas no coinciden";
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
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });

      if (!response.ok) {
        const data = (await response.json()) as { detail?: unknown };
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : "Error al restablecer la contraseña";
        setError(msg);
        return;
      }

      // Éxito: redirigir a login
      router.push("/login?reset=ok");
    } catch {
      setError("No se pudo conectar con el servidor. Inténtalo de nuevo.");
    } finally {
      setSubmitting(false);
    }
  }

  // Si no hay token en la URL, mostrar un mensaje de error
  if (!token) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">
            HealthCore
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Enlace inválido</h1>
          <p className="mt-2 text-sm text-slate-600">
            El enlace de restablecimiento no es válido o ha expirado.
            Solicita uno nuevo para continuar.
          </p>
          <p className="mt-6">
            <Link
              href="/forgot-password"
              className="rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700"
            >
              Solicitar un nuevo enlace
            </Link>
          </p>
        </div>
      </main>
    );
  }

  // Token presente pero inválido/expirado devuelto por la API (400).
  const tokenRejected =
    error && error.includes("no es válido") || error === "El enlace de restablecimiento no es válido o ha expirado.";

  return (
    <main className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <div className="w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">
          HealthCore
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Nueva contraseña</h1>
        <p className="mt-1 text-sm text-slate-600">
          Establece una nueva contraseña para tu cuenta.
        </p>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <p className="font-medium">{error}</p>
            {tokenRejected && (
              <p className="mt-2">
                <Link
                  href="/forgot-password"
                  className="font-semibold text-red-800 underline hover:text-red-900"
                >
                  Solicitar un nuevo enlace
                </Link>
              </p>
            )}
          </div>
        )}

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Nueva contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                setError(null);
              }}
              placeholder="Mínimo 8 caracteres"
              autoComplete="new-password"
              disabled={submitting}
              required
              minLength={8}
            />
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Confirmar contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setError(null);
              }}
              placeholder="Repite la nueva contraseña"
              autoComplete="new-password"
              disabled={submitting}
              required
              minLength={8}
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
          >
            {submitting ? "Restableciendo..." : "Restablecer contraseña"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          <Link href="/login" className="font-semibold text-cyan-700 hover:text-cyan-800">
            Volver a iniciar sesión
          </Link>
        </p>
      </div>
    </main>
  );
}