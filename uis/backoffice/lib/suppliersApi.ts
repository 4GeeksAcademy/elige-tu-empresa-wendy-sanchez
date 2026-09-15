import type { Supplier, SupplierCreatePayload, SupplierFilters, SupplierStatus } from "../types/supplier";
import { getToken, removeToken } from "./auth";

function handle401() {
  if (typeof window !== "undefined") {
    removeToken();
    window.location.href = "/login";
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) ?? {}),
    ...getAuthHeaders(),
  };

  const response = await fetch(url, { ...init, headers });

  if (response.status === 401) {
    handle401();
    throw new Error("Sesión expirada. Redirigiendo al inicio de sesión...");
  }

  if (!response.ok) {
    throw new Error("Error de comunicación con el servidor. Inténtalo de nuevo.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export function fetchSuppliers(filters: SupplierFilters = {}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return request<Supplier[]>(`/api/suppliers${query ? `?${query}` : ""}`);
}

export function createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
  return request<Supplier>("/api/suppliers", jsonInit("POST", payload));
}

export function updateSupplierRate(id: number, monthlyRate: number): Promise<Supplier> {
  return request<Supplier>(`/api/suppliers/${id}/rate`, jsonInit("PATCH", { monthly_rate: monthlyRate }));
}

export function updateSupplierStatus(id: number, status: SupplierStatus): Promise<Supplier> {
  return request<Supplier>(`/api/suppliers/${id}/status`, jsonInit("PATCH", { status }));
}

export function archiveSupplier(id: number): Promise<Supplier> {
  return request<Supplier>(`/api/suppliers/${id}`, { method: "DELETE" });
}
