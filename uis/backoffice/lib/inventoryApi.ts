/** Cliente HTTP para la API de inventario de HealthCore.
 *
 * Centraliza todas las llamadas a los endpoints /inventory del backend.
 * Las peticiones se realizan a través del proxy de Next.js (/api/inventory/*)
 * configurado en next.config.ts para evitar problemas de CORS.
 *
 * NINGÚN componente debe llamar a fetch directamente.
 * La capa HTTP (request<T>, jsonRequest, extractErrorMessage) está delegada
 * en ./httpClient.ts, el cliente HTTP único del backoffice.
 *
 * @module inventoryApi
 */

import { request } from "./httpClient";

// ── Tipos ─────────────────────────────────────────────────────────────

export interface MedicalSupply {
  id: number;
  name: string;
  sku: string;
  category: string;
  unit: string;
  country: string;
  current_stock: number;
}

export interface SupplyDeliveryCreate {
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
}

export interface SupplyDeliveryResponse {
  id: number;
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface SupplyConsumptionCreate {
  supply_id: number;
  quantity: number;
  consumption_type: string;
  clinic_id: number;
}

export interface SupplyConsumptionResponse {
  id: number;
  supply_id: number;
  quantity: number;
  consumption_type: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface OrderItem {
  id: number;
  type: string; // "delivery" | "consumption"
  supply_id: number;
  supply_name: string;
  supply_sku: string;
  quantity: number;
  detail: string; // vendor_name o consumption_type
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface OrderListResponse {
  orders: OrderItem[];
}

// ── Constantes ────────────────────────────────────────────────────────

/** Stock mínimo saludable — por debajo de este umbral se marca como "bajo".
 *  Umbral elegido: < 20 unidades o < 10% del lote típico.
 *  Se usa para el código de color en la vista de productos.
 */
const STOCK_LOW_THRESHOLD = 20;

/** Stock crítico — por debajo se marca como "crítico".
 *  Umbral elegido: 0 unidades (sin stock).
 */
const STOCK_CRITICAL_THRESHOLD = 0;

// ── Helpers de clasificación de stock ─────────────────────────────────

export type StockLevel = "healthy" | "low" | "critical";

export function getStockLevel(stock: number): StockLevel {
  if (stock <= STOCK_CRITICAL_THRESHOLD) return "critical";
  if (stock < STOCK_LOW_THRESHOLD) return "low";
  return "healthy";
}

export function getStockLevelLabel(stock: number): string {
  const level = getStockLevel(stock);
  switch (level) {
    case "critical": return "Sin stock";
    case "low": return "Stock bajo";
    case "healthy": return "Disponible";
  }
}

export function getStockLevelColor(stock: number): string {
  const level = getStockLevel(stock);
  switch (level) {
    case "critical": return "text-red-600 bg-red-50 border-red-200";
    case "low": return "text-amber-600 bg-amber-50 border-amber-200";
    case "healthy": return "text-emerald-600 bg-emerald-50 border-emerald-200";
  }
}

// ── Cliente HTTP ──────────────────────────────────────────────────────

/** Desde el navegador, las peticiones pasan por el proxy de Next.js
 *  (/api/inventory/*) configurado en next.config.ts, que reescribe
 *  a http://backend:8000/inventory/*. Desde el servidor (SSR)
 *  se usa la variable NEXT_PUBLIC_INVENTORY_API_URL.
 */
const API_BASE_URL = typeof window !== "undefined"
  ? ""  // En el navegador, usar ruta relativa → Next.js proxy
  : (process.env.NEXT_PUBLIC_INVENTORY_API_URL ?? "http://backend:8000");

function apiPath(endpoint: string): string {
  // Los endpoints ya incluyen /inventory/ (ej: "/inventory/products")
  return typeof window !== "undefined"
    ? `/api${endpoint}`  // → "/api/inventory/products" (coincide con el rewrite)
    : `${API_BASE_URL}${endpoint}`;
}

// Note: handle401(), getAuthHeaders(), request<T>(), extractErrorMessage(),
// ApiError, ValidationIssue están ahora en ./httpClient.ts (único punto de mantenimiento).

async function requestInventory<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(apiPath(path), init);
}

// ── Endpoints ─────────────────────────────────────────────────────────

/** Obtiene todos los suministros médicos con su stock actual. GET /inventory/products */
export function fetchProducts(): Promise<MedicalSupply[]> {
  return requestInventory<MedicalSupply[]>("/inventory/products");
}

/** Obtiene un suministro por ID con su stock calculado. GET /inventory/products/{id} */
export function fetchProduct(id: number): Promise<MedicalSupply> {
  return requestInventory<MedicalSupply>(`/inventory/products/${id}`);
}

/** Registra un nuevo suministro médico. POST /inventory/products */
export function createProduct(payload: {
  name: string;
  sku: string;
  category: string;
  unit: string;
  country: string;
}): Promise<MedicalSupply> {
  return requestInventory<MedicalSupply>("/inventory/products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Registra una orden de entrada (entrega de proveedor). POST /inventory/orders/inbound */
export function createInboundOrder(payload: SupplyDeliveryCreate): Promise<SupplyDeliveryResponse> {
  return requestInventory<SupplyDeliveryResponse>("/inventory/orders/inbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Registra una orden de salida (consumo clínico). POST /inventory/orders/outbound */
export function createOutboundOrder(payload: SupplyConsumptionCreate): Promise<SupplyConsumptionResponse> {
  return requestInventory<SupplyConsumptionResponse>("/inventory/orders/outbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Obtiene el historial completo de órdenes (entradas y salidas). GET /inventory/orders */
export function fetchOrders(): Promise<OrderListResponse> {
  return requestInventory<OrderListResponse>("/inventory/orders");
}