import type { Supplier, SupplierCreatePayload, SupplierFilters, SupplierStatus } from "../types/supplier";
import { request, jsonRequest } from "./httpClient";

export function fetchSuppliers(filters: SupplierFilters = {}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return request<Supplier[]>(`/api/suppliers${query ? `?${query}` : ""}`);
}

export function createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
  return jsonRequest<Supplier>("POST", "/api/suppliers", payload);
}

export function updateSupplierRate(id: number, monthlyRate: number): Promise<Supplier> {
  return jsonRequest<Supplier>("PATCH", `/api/suppliers/${id}/rate`, { monthly_rate: monthlyRate });
}

export function updateSupplierStatus(id: number, status: SupplierStatus): Promise<Supplier> {
  return jsonRequest<Supplier>("PATCH", `/api/suppliers/${id}/status`, { status });
}

export function archiveSupplier(id: number): Promise<Supplier> {
  return request<Supplier>(`/api/suppliers/${id}`, { method: "DELETE" });
}
