"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  getToken,
  removeToken,
  setToken,
  type MeResponse,
} from "@/lib/auth";

interface AuthContextValue {
  /** El usuario autenticado, o null mientras no se haya cargado / no haya sesión. */
  user: MeResponse | null;
  /** true mientras se está verificando la sesión existente. */
  loading: boolean;
  /** Almacena un token y redirige al dashboard. */
  login: (token: string) => void;
  /** Elimina el token, limpia el estado y redirige al login. */
  logout: () => void;
  /** Recarga los datos del usuario desde GET /auth/me. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = (await response.json()) as MeResponse;
        setUser(data);
      } else {
        // Token inválido o expirado → limpiar
        removeToken();
        setUser(null);
      }
    } catch {
      // Error de red: no se puede verificar, pero mantenemos el token
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchUser();
  }, [fetchUser]);

  const login = useCallback(
    (token: string) => {
      setToken(token);
      setUser(null); // se recargará vía refreshUser
      router.push("/");
    },
    [router],
  );

  const logout = useCallback(() => {
    removeToken();
    setUser(null);
    router.push("/login");
  }, [router]);

  const refreshUser = useCallback(async () => {
    await fetchUser();
  }, [fetchUser]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Hook para acceder al contexto de autenticación. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth debe usarse dentro de un <AuthProvider>");
  }
  return ctx;
}