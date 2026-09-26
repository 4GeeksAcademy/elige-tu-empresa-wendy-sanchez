/** Tests for lib/suppliersApi.ts — CRUD client for suppliers backend. */

import {
  fetchSuppliers,
  createSupplier,
  archiveSupplier,
  updateSupplierRate,
  updateSupplierStatus,
} from "../lib/suppliersApi";

// ---------------------------------------------------------------------------
//  Mock dependencies
// ---------------------------------------------------------------------------

jest.mock("../lib/auth", () => ({
  getToken: jest.fn(),
  removeToken: jest.fn(),
}));

import { getToken, removeToken } from "../lib/auth";

const mockGetToken = getToken as jest.Mock;
const mockRemoveToken = removeToken as jest.Mock;

// ---------------------------------------------------------------------------
//  Mock global fetch
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

const MOCK_SUPPLIER = {
  id: 1,
  name: "Test Supplier",
  country: "USA",
  categories: ["medical_supplies"],
  monthly_rate: 1500,
  currency: "USD",
  updated_at: "2025-01-01T00:00:00Z",
  archived_at: null,
  status: "active",
  compliance_agreement: "BAA",
  contract_renewal_date: "2026-01-01",
  contact_email: "supplier@test.com",
  notes: null,
};

function mockResponse(body: unknown, status = 200): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

function mockJsonResponse(body: unknown, status = 200): Response {
  return mockResponse(body, status);
}

beforeEach(() => {
  jest.resetAllMocks();
  mockGetToken.mockReturnValue("valid-token");
});

// ---------------------------------------------------------------------------
//  fetchSuppliers
// ---------------------------------------------------------------------------

describe("fetchSuppliers()", () => {
  it("happy path: retorna lista de proveedores filtrada por país", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([MOCK_SUPPLIER]));

    const result = await fetchSuppliers({ country: "USA" });
    expect(result).toEqual([MOCK_SUPPLIER]);

    // Verifica que llamó a fetch con la URL correcta
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/api/suppliers");
    expect(url).toContain("country=USA");
  });

  it("happy path: retorna todos sin filtros", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([MOCK_SUPPLIER]));

    const result = await fetchSuppliers({});
    expect(result).toEqual([MOCK_SUPPLIER]);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toBe("/api/suppliers");
  });

  it("failure mode: 401 redirige al login y llama removeToken", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ detail: "Unauthorized" }, 401));
    // Suprimir console.error de jsdom por navegación no implementada
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    await expect(fetchSuppliers({})).rejects.toThrow("Sesión expirada");
    expect(mockRemoveToken).toHaveBeenCalled();

    spy.mockRestore();
  });

  it("failure mode: error de red lanza excepción", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(fetchSuppliers({})).rejects.toThrow(TypeError);
  });

  it("failure mode: respuesta no-ok lanza excepción con mensaje del servidor", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ detail: "Server error" }, 500));

    await expect(fetchSuppliers({})).rejects.toThrow("Server error");
  });
});

// ---------------------------------------------------------------------------
//  createSupplier
// ---------------------------------------------------------------------------

describe("createSupplier()", () => {
  const PAYLOAD = {
    name: "New Supplier",
    country: "USA" as const,
    categories: ["medical_supplies"] as const,
    monthly_rate: 2000,
    currency: "USD" as const,
    compliance_agreement: "DPA" as const,
    contract_renewal_date: "2026-06-01",
    contact_email: "new@supplier.com",
    notes: "Test supplier",
  };

  it("happy path: crea proveedor y retorna el objeto", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse(MOCK_SUPPLIER, 201));

    const result = await createSupplier(PAYLOAD);
    expect(result).toEqual(MOCK_SUPPLIER);

    // Verifica que envió POST con JSON
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/suppliers");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "content-type": "application/json" });
    expect(init.body).toBe(JSON.stringify(PAYLOAD));
  });

  it("failure mode: error de red lanza excepción", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Network error"));

    await expect(createSupplier(PAYLOAD)).rejects.toThrow(TypeError);
  });

  it("failure mode: 422 lanza excepción con detalle del servidor", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ detail: "Validation error" }, 422));

    await expect(createSupplier(PAYLOAD)).rejects.toThrow("Validation error");
  });
});

// ---------------------------------------------------------------------------
//  archiveSupplier
// ---------------------------------------------------------------------------

describe("archiveSupplier()", () => {
  it("happy path: elimina y retorna undefined (204)", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse(null, 204));

    const result = await archiveSupplier(1);
    expect(result).toBeUndefined();

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/suppliers/1");
    expect(init.method).toBe("DELETE");
  });

  it("failure mode: 404 lanza excepción con detalle del servidor", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ detail: "Not found" }, 404));

    await expect(archiveSupplier(999)).rejects.toThrow("Not found");
  });
});

// ---------------------------------------------------------------------------
//  updateSupplierRate
// ---------------------------------------------------------------------------

describe("updateSupplierRate()", () => {
  it("happy path: actualiza tarifa y retorna proveedor", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse(MOCK_SUPPLIER));

    const result = await updateSupplierRate(1, 2500);
    expect(result).toEqual(MOCK_SUPPLIER);

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/suppliers/1/rate");
    expect(init.method).toBe("PATCH");
    expect(init.body).toContain("2500");
  });

  it("failure mode: error de red", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network down"));

    await expect(updateSupplierRate(1, 999)).rejects.toThrow("Network down");
  });
});

// ---------------------------------------------------------------------------
//  updateSupplierStatus
// ---------------------------------------------------------------------------

describe("updateSupplierStatus()", () => {
  it("happy path: cambia estado y retorna proveedor", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ ...MOCK_SUPPLIER, status: "suspended" }));

    const result = await updateSupplierStatus(1, "suspended");
    expect(result).toEqual({ ...MOCK_SUPPLIER, status: "suspended" });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/suppliers/1/status");
    expect(init.method).toBe("PATCH");
    expect(init.body).toContain("suspended");
  });

  it("failure mode: 401 redirige", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({}, 401));
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    await expect(updateSupplierStatus(1, "active")).rejects.toThrow("Sesión expirada");
    expect(mockRemoveToken).toHaveBeenCalled();

    spy.mockRestore();
  });
});