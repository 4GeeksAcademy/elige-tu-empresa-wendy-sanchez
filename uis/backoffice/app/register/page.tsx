"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";

interface FieldErrors {
  email?: string;
  password?: string;
  name?: string;
  phone?: string;
  address?: string;
  general?: string;
}

export default function RegisterPage() {
  const { login } = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    phone: "",
    address: "",
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function setField<K extends keyof typeof form>(field: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined, general: undefined }));
  }

  function validate(): FieldErrors {
    const errs: FieldErrors = {};
    if (!form.email.trim()) errs.email = "El email es obligatorio";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
      errs.email = "Introduce un email válido";
    if (!form.password) errs.password = "La contraseña es obligatoria";
    else if (form.password.length < 8) errs.password = "Mínimo 8 caracteres";
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

      // 1) Crear usuario
      const createPayload: Record<string, unknown> = { email: form.email.trim(), password: form.password };
      if (form.name.trim()) createPayload.name = form.name.trim();
      if (form.phone.trim()) createPayload.phone = form.phone.trim();
      if (form.address.trim()) createPayload.address = form.address.trim();

      const createResponse = await fetch("/api/users", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(createPayload),
      });

      const createData = (await createResponse.json()) as { detail?: string | unknown };

      if (!createResponse.ok) {
        setErrors({ general: "No se pudo crear la cuenta. Verifica los datos e inténtalo de nuevo." });
        return;
      }

      // 2) Iniciar sesión automáticamente después del registro
      const loginResponse = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: form.email.trim(), password: form.password }),
      });

      const loginData = (await loginResponse.json()) as { access_token?: string; detail?: string };

      if (!loginResponse.ok || !loginData.access_token) {
        setErrors({ general: "Cuenta creada, pero no se pudo iniciar sesión automáticamente. Intenta iniciar sesión manualmente." });
        return;
      }

      login(loginData.access_token);
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
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Crear cuenta</h1>
        <p className="mt-1 text-sm text-slate-600">
          Regístrate para acceder al panel de operaciones internas.
        </p>

        {errors.general && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {errors.general}
          </div>
        )}

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          {/* Email */}
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Email *</span>
            <input
              type="email"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={form.email}
              onChange={(e) => setField("email", e.target.value)}
              placeholder="usuario@healthcore.com"
              required
            />
            {errors.email && <span className="text-sm text-red-700">{errors.email}</span>}
          </label>

          {/* Contraseña */}
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Contraseña *</span>
            <input
              type="password"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={form.password}
              onChange={(e) => setField("password", e.target.value)}
              placeholder="Mínimo 8 caracteres"
              required
              minLength={8}
            />
            {errors.password && <span className="text-sm text-red-700">{errors.password}</span>}
          </label>

          {/* Nombre */}
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Nombre completo</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={form.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Opcional"
            />
            {errors.name && <span className="text-sm text-red-700">{errors.name}</span>}
          </label>

          {/* Teléfono */}
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Teléfono</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={form.phone}
              onChange={(e) => setField("phone", e.target.value)}
              placeholder="Opcional"
            />
            {errors.phone && <span className="text-sm text-red-700">{errors.phone}</span>}
          </label>

          {/* Dirección */}
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Dirección</span>
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-cyan-600 focus:ring"
              value={form.address}
              onChange={(e) => setField("address", e.target.value)}
              placeholder="Opcional"
            />
            {errors.address && <span className="text-sm text-red-700">{errors.address}</span>}
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
          >
            {submitting ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          ¿Ya tienes cuenta?{" "}
          <Link href="/login" className="font-semibold text-cyan-700 hover:text-cyan-800">
            Inicia sesión
          </Link>
        </p>
      </div>
    </main>
  );
}