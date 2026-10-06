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
import { beginTelemetrySession } from "@/lib/telemetrySession";
import { track } from "@/lib/telemetry";
import { reportLoginFailure, reportSessionExpired } from "@/lib/telemetryAuth";

interface AuthContextValue {
  /** El usuario autenticado, o null mientras no se haya cargado / no haya sesión. */
  user: MeResponse | null;
  /** true mientras se está verificando la sesión existente. */
  loading: boolean;
  /** Almacena un token y redirige al dashboard. */
  login: (token: string) => Promise<void>;
  authenticate: (email: string, password: string) => Promise<void>;
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

    beginTelemetrySession();
    try {
      const response = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data = (await response.json()) as MeResponse;
        beginTelemetrySession(data.telemetry_user_id);
        setUser(data);
      } else {
        if (response.status === 401) reportSessionExpired();
        // Token inválido o expirado → limpiar
        console.error("Token inválido o expirado, limpiando sesión (status %d)", response.status);
        removeToken();
        setUser(null);
      }
    } catch {
      // Error de red: no se puede verificar, pero mantenemos el token
      console.error("Error de red al verificar sesión en /api/auth/me");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchUser();
  }, [fetchUser]);

  const login = useCallback(
    async (token: string) => {
      setToken(token);
      // Recargar los datos del usuario antes de navegar
      try {
        const response = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = (await response.json()) as MeResponse;
          beginTelemetrySession(data.telemetry_user_id);
          setUser(data);
          track("auth_login_succeeded", {
            application: "backoffice", role_group: data.role === "admin" ? "admin" : "staff",
            country: "unknown", auth_method: "password",
          });
        } else {
          reportSessionExpired();
          removeToken();
          reportLoginFailure("session_expired");
          throw new Error("La sesión no pudo validarse. Inicia sesión de nuevo.");
        }
      } catch {
        console.error("Error al cargar perfil de usuario tras login");
        setUser(null);
        removeToken();
        throw new Error("No se pudo validar la sesión.");
      }
      router.push("/");
    },
    [router],
  );

  const authenticate = useCallback(async (email: string, password: string) => {
    let response: Response;
    try {
      response = await fetch("/api/auth/login", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      reportLoginFailure("network_error");
      throw new Error("No se pudo conectar con el servidor. Inténtalo de nuevo.");
    }
    if (!response.ok) {
      reportLoginFailure(response.status >= 500 ? "service_error" : "invalid_credentials", response.status === 429);
      throw new Error("No se pudo iniciar sesión. Comprueba tus credenciales.");
    }
    const data = await response.json() as { access_token?: string };
    if (!data.access_token) {
      reportLoginFailure("service_error");
      throw new Error("Respuesta de autenticación inválida.");
    }
    await login(data.access_token);
  }, [login]);

  const logout = useCallback(() => {
    track("auth_logout_completed", { application: "backoffice", logout_reason: "user_action" });
    removeToken();
    setUser(null);
    router.push("/login");
  }, [router]);

  const refreshUser = useCallback(async () => {
    await fetchUser();
  }, [fetchUser]);

  return (
    <AuthContext.Provider value={{ user, loading, login, authenticate, logout, refreshUser }}>
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