/**
 * Cliente HTTP autenticado único para el backoffice.
 *
 * ── Responsabilidades ─────────────────────────────────────────────────
 * 1. Leer el token JWT de localStorage (via auth.ts).
 * 2. Adjuntar Authorization: Bearer en cada petición.
 * 3. Si la API responde 401, limpiar el token y redirigir a /login.
 * 4. Extraer mensajes de error del cuerpo de la respuesta (Pydantic-style).
 * 5. Exponer helpers para JSON requests (jsonRequest).
 *
 * ── Uso ───────────────────────────────────────────────────────────────
 *   import { request, jsonRequest } from "@/lib/httpClient";
 *
 *   const data = await request<T[]>("/api/items");
 *   const created = await jsonRequest<T>("POST", "/api/items", payload);
 *
 * ── Historia ──────────────────────────────────────────────────────────
 * Consolidación de authHttpClient.ts, suppliersApi.ts e inventoryApi.ts
 * que implementaban el mismo patrón fetch+JWT+error 3 veces (~150 líneas
 * duplicadas). Ver AUDIT.md Caso 2 y REPORT.md.
 *
 * @module httpClient
 */

import { getToken, removeToken } from "./auth";

// ── Tipos auxiliares ──────────────────────────────────────────────────

export interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

/**
 * Error con código de estado HTTP.
 * Lanzado por request() cuando la respuesta no es ok.
 */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ── Extracción de errores ─────────────────────────────────────────────

/**
 * Extrae un mensaje legible del cuerpo de error devuelto por FastAPI.
 *
 * Soporta dos formatos:
 *   - Pydantic v2: { "detail": [ { "loc": ["body", "email"], "msg": "..." } ] }
 *   - HTTPException: { "detail": "mensaje string" }
 */
export function extractErrorMessage(payload: unknown, fallback: string): string {
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

// ── Manejo de 401 ─────────────────────────────────────────────────────

function handle401(): void {
  if (typeof window !== "undefined") {
    removeToken();
    window.location.href = "/login";
  }
}

// ── Request genérico ──────────────────────────────────────────────────

/**
 * Ejecuta una petición HTTP autenticada con tipado fuerte.
 *
 * - Adjunta automáticamente el JWT de localStorage.
 * - Si la respuesta es 401, redirige a /login.
 * - Si la respuesta es 204 (sin contenido), devuelve `undefined` como T.
 * - Lanza `ApiError` con el mensaje extraído del body en caso de error.
 *
 * @param url  URL completa de la petición.
 * @param init Opciones fetch adicionales (method, headers, body, etc.).
 * @returns    Promesa del tipo T.
 */
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
    throw new ApiError("Sesión expirada. Redirigiendo al inicio de sesión...", 401);
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      extractErrorMessage(payload, `La API respondió con estado ${response.status}`),
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// ── Helpers para métodos HTTP comunes ─────────────────────────────────

/**
 * Helper para peticiones con body JSON (POST, PUT, PATCH).
 *
 * @example
 *   const newItem = await jsonRequest<Item>("POST", "/api/items", { name: "Foo" });
 */
export function jsonRequest<T>(method: string, url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

/**
 * Alias de `request()` para compatibilidad.
 * @deprecated Usa `request()` o `jsonRequest()` directamente.
 */
export async function requestAuth<T>(url: string, init?: RequestInit): Promise<T> {
  return request<T>(url, init);
}