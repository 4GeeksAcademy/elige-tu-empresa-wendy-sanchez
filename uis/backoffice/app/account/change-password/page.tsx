"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { getToken } from "@/lib/auth";

interface FieldErrors {
  currentPassword?: string;
  newPassword?: string;
  confirmPassword?: string;
  general?: string;
  success?: string;
}

/**
 * Página de cambio de contraseña (usuario autenticado).
 *
 * - Pide la contraseña actual, la nueva y la confirmación.
 * - Valida que la nueva contraseña y la confirmación coinciden ANTES de
 *   llamar a la API.
 */
export default function ChangePasswordPage() {
  const { user, loading, logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): FieldErrors {
    const errs: FieldErrors = {};
    if (!currentPassword) errs.currentPassword = "La contraseña actual es obligatoria";
    if (!newPassword) errs.newPassword = "La nueva contraseña es obligatoria";
    else if (newPassword.length < 8)
      errs.newPassword = "La nueva contraseña debe tener al menos 8 caracteres";
    if (!confirmPassword) errs.confirmPassword = "Confirma la nueva contraseña";
    else if (confirmPassword !== newPassword)
      errs.confirmPassword = "Las contraseñas no coinciden";
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

    const token = getToken();
    if (!token) {
      logout();
      return;
    }

    try {
      setSubmitting(true);
      const response = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (response.status === 401) {
        logout();
        return;
      }

      if (!response.ok) {
        const data = (await response.json()) as { detail?: unknown };
        const msg =
          typeof data.detail === "string" ? data.detail : "Error al cambiar la contraseña";
        setErrors({ general: msg });
        return;
      }

      // Limpiar campos y mostrar confirmación
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setErrors({ success: "Contraseña actualizada correctamente." });
    } catch {
      setErrors({ general: "No se pudo conectar con el servidor. Inténtalo de nuevo." });
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-80px)] max-w-lg items-center justify-center px-4 py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-600 border-t-transparent" />
      </main>
    );
  }

  if (!user) {
    return null; // AuthGuard redirigirá al login
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">
          HealthCore
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Cambiar contraseña</h1>
        <p className="mt-1 text-sm text-slate-600">
          Actualiza la contraseña de acceso a tu cuenta.
        </p>

        {errors.success && (
          <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            {errors.success}
          </div>
        )}

        {errors.general && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {errors.general}
          </div>
        )}

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Contraseña actual</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={currentPassword}
              onChange={(e) => {
                setCurrentPassword(e.target.value);
                setErrors({});
              }}
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={submitting}
              required
            />
            {errors.currentPassword && (
              <span className="text-sm text-red-700">{errors.currentPassword}</span>
            )}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Nueva contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                setErrors({});
              }}
              placeholder="Mínimo 8 caracteres"
              autoComplete="new-password"
              disabled={submitting}
              required
              minLength={8}
            />
            {errors.newPassword && (
              <span className="text-sm text-red-700">{errors.newPassword}</span>
            )}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Confirmar nueva contraseña</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setErrors({});
              }}
              placeholder="Repite la nueva contraseña"
              autoComplete="new-password"
              disabled={submitting}
              required
              minLength={8}
            />
            {errors.confirmPassword && (
              <span className="text-sm text-red-700">{errors.confirmPassword}</span>
            )}
          </label>

          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
            >
              {submitting ? "Guardando..." : "Actualizar contraseña"}
            </button>
            <Link
              href="/account/profile"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Volver a mi cuenta
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}