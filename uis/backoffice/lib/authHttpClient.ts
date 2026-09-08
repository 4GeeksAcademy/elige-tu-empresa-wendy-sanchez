/**
 * Cliente HTTP autenticado para el backoffice.
 * - Lee el token JWT de localStorage.
 * - Lo adjunta como Authorization: Bearer en cada petición.
 * - Si la API responde con 401, limpia el token y redirige a /login.
 */

import { getToken, removeToken } from "./auth";

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return fallback;
  }

  const detail = (payload as { detail: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = (detail as ValidationIssue[])
      .map((issue) => {
        const field = issue.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg ?? "valor inválido"}` : issue.msg;
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join(" · ");
    }
  }

  return fallback;
}

function handle401() {
  if (typeof window !== "undefined") {
    removeToken();
    window.location.href = "/login";
  }
}

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) ?? {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    handle401();
    // La redirección ocurre arriba; lanzamos error para detener el flujo
    throw new Error("Sesión expirada. Redirigiendo al inicio de sesión...");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(extractErrorMessage(payload, `La API respondió con estado ${response.status}`));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function requestAuth<T>(url: string, init?: RequestInit): Promise<T> {
  return request<T>(url, init);
}