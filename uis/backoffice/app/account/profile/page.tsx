"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { getToken, type MeResponse, type Profile, type ProfileUpdate } from "@/lib/auth";

interface FieldErrors {
  name?: string;
  phone?: string;
  address?: string;
  general?: string;
  success?: string;
}

export default function ProfilePage() {
  const { user, loading, logout, refreshUser } = useAuth();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  // Inicializa los campos del formulario con los datos del perfil
  useEffect(() => {
    if (user?.profile) {
      setName(user.profile.name ?? "");
      setPhone(user.profile.phone ?? "");
      setAddress(user.profile.address ?? "");
    }
  }, [user]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});

    const token = getToken();
    if (!token) {
      logout();
      return;
    }

    const payload: ProfileUpdate = {
      name: name.trim() || null,
      phone: phone.trim() || null,
      address: address.trim() || null,
    };

    try {
      setSubmitting(true);
      const response = await fetch("/api/profiles/me", {
        method: "PUT",
        headers: {
          "content-type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 401) {
        logout();
        return;
      }

      if (!response.ok) {
        const data = (await response.json()) as { detail?: unknown };
        const msg = typeof data.detail === "string" ? data.detail : "Error al actualizar el perfil";
        setErrors({ general: msg });
        return;
      }

      await refreshUser();
      setErrors({ success: "Perfil actualizado correctamente." });
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
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Mi cuenta</h1>
        <p className="mt-1 text-sm text-slate-600">
          Gestiona tu información personal y de contacto.
        </p>

        {/* Email (no editable) */}
        <div className="mt-6 rounded-lg bg-slate-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Email</p>
          <p className="mt-1 text-sm font-medium text-slate-900">{user.email}</p>
        </div>

        {/* Rol */}
        <div className="mt-2 rounded-lg bg-slate-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Rol</p>
          <p className="mt-1 text-sm font-medium text-slate-900 capitalize">{user.role}</p>
        </div>

        {/* Enlace a cambio de contraseña */}
        <div className="mt-2">
          <Link
            href="/account/change-password"
            className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-slate-50"
          >
            Cambiar contraseña
          </Link>
        </div>

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
            <span className="text-sm font-medium text-slate-700">Nombre completo</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setErrors({});
              }}
              placeholder="Tu nombre"
            />
            {errors.name && <span className="text-sm text-red-700">{errors.name}</span>}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Teléfono</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                setErrors({});
              }}
              placeholder="+1 555 123 4567"
            />
            {errors.phone && <span className="text-sm text-red-700">{errors.phone}</span>}
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Dirección</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={address}
              onChange={(e) => {
                setAddress(e.target.value);
                setErrors({});
              }}
              placeholder="123 Main St, City"
            />
            {errors.address && <span className="text-sm text-red-700">{errors.address}</span>}
          </label>

          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
            >
              {submitting ? "Guardando..." : "Guardar cambios"}
            </button>
            <Link
              href="/"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Volver al dashboard
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}