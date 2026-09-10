/** Tipos compartidos para el flujo de autenticación. */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string | null;
  phone?: string | null;
  address?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Profile {
  id: number;
  user_id: number;
  name: string | null;
  phone: string | null;
  address: string | null;
}

export interface MeResponse {
  email: string;
  role: string;
  profile: Profile | null;
}

export interface ProfileUpdate {
  name?: string | null;
  phone?: string | null;
  address?: string | null;
}

const TOKEN_KEY = "healthcore_token";

/** Recupera el token JWT almacenado en localStorage. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** Almacena el token JWT en localStorage. */
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

/** Elimina el token JWT de localStorage (cierre de sesión). */
export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Construye la cabecera Authorization: Bearer a partir del token almacenado. */
export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}