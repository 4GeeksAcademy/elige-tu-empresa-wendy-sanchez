/** Tests for lib/auth.ts — localStorage-based JWT management. */

import { getToken, setToken, removeToken, getAuthHeaders } from "../lib/auth";

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
});

// ---------------------------------------------------------------------------
//  getToken
// ---------------------------------------------------------------------------

describe("getToken()", () => {
  it("retorna el token cuando existe en localStorage", () => {
    localStorage.setItem("healthcore_token", "my-jwt-token");
    expect(getToken()).toBe("my-jwt-token");
  });

  it("retorna null cuando no hay token almacenado", () => {
    expect(getToken()).toBeNull();
  });

  it("retorna null si typeof window es undefined (SSR)", () => {
    const origWindow = (globalThis as Record<string, unknown>).window;
    (globalThis as Record<string, unknown>).window = undefined;

    expect(getToken()).toBeNull();

    (globalThis as Record<string, unknown>).window = origWindow;
  });
});

// ---------------------------------------------------------------------------
//  setToken
// ---------------------------------------------------------------------------

describe("setToken()", () => {
  it("almacena el token en localStorage", () => {
    setToken("new-token");
    expect(localStorage.getItem("healthcore_token")).toBe("new-token");
  });

  it("reemplaza un token existente", () => {
    localStorage.setItem("healthcore_token", "old-token");
    setToken("updated-token");
    expect(localStorage.getItem("healthcore_token")).toBe("updated-token");
  });

  it("acepta token vacío", () => {
    setToken("");
    expect(localStorage.getItem("healthcore_token")).toBe("");
  });
});

// ---------------------------------------------------------------------------
//  removeToken
// ---------------------------------------------------------------------------

describe("removeToken()", () => {
  it("elimina el token de localStorage", () => {
    localStorage.setItem("healthcore_token", "to-remove");
    removeToken();
    expect(localStorage.getItem("healthcore_token")).toBeNull();
  });

  it("no falla si no hay token", () => {
    expect(() => removeToken()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
//  getAuthHeaders
// ---------------------------------------------------------------------------

describe("getAuthHeaders()", () => {
  it("retorna cabecera Authorization cuando hay token", () => {
    localStorage.setItem("healthcore_token", "bearer-token");
    const headers = getAuthHeaders();
    expect(headers).toEqual({ Authorization: "Bearer bearer-token" });
  });

  it("retorna objeto vacío cuando no hay token", () => {
    expect(getAuthHeaders()).toEqual({});
  });

  it("retorna objeto vacío si el token es cadena vacía (truthy check)", () => {
    localStorage.setItem("healthcore_token", "");
    const headers = getAuthHeaders();
    // Cadena vacía es falsy → getToken la trata como "no token"
    expect(headers).toEqual({});
  });
});