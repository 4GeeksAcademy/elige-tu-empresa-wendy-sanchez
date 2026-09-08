"use client";

import { AuthProvider } from "@/lib/AuthContext";
import AuthGuard from "@/components/AuthGuard";
import BackofficeHeader from "@/components/BackofficeHeader";

interface AuthShellProps {
  children: React.ReactNode;
}

/**
 * Shell cliente que engloba toda la aplicación del backoffice.
 * - AuthProvider: contexto de autenticación para toda la app.
 * - AuthGuard: protege las rutas contra acceso no autenticado.
 * - BackofficeHeader: barra superior con navegación y control de sesión.
 */
export default function AuthShell({ children }: AuthShellProps) {
  return (
    <AuthProvider>
      <BackofficeHeader />
      <AuthGuard>{children}</AuthGuard>
    </AuthProvider>
  );
}