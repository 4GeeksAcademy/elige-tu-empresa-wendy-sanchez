import type { Supplier } from "../types/supplier";

const BACKEND_URL =
  process.env.SUPPLIERS_API_URL ?? process.env.INCIDENTS_API_URL ?? "http://127.0.0.1:8000";

export interface InitialSuppliers {
  suppliers: Supplier[];
  error: string | null;
}

export async function loadInitialSuppliers(): Promise<InitialSuppliers> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/suppliers`, { cache: "no-store" });

    if (!response.ok) {
      return {
        suppliers: [],
        error: `La API de proveedores respondió con estado ${response.status}`,
      };
    }

    return { suppliers: (await response.json()) as Supplier[], error: null };
  } catch {
    return {
      suppliers: [],
      error:
        "No se pudo contactar con la API de proveedores. Arráncala con: cd services/api && uv run uvicorn main:app --port 8000",
    };
  }
}
