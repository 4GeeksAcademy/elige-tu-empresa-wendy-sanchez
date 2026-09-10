"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/AuthContext";

/** Rutas públicas que no requieren autenticación. */
const PUBLIC_ROUTES = ["/login", "/register", "/forgot-password", "/reset-password"];

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * Componente que protege las rutas del backoffice. Si el usuario no está
 * autenticado (no hay token) y la ruta no es pública, redirige a /login.
 * Mientras verifica la sesión muestra un spinner de carga.
 */
export default function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + "/"),
  );

  useEffect(() => {
    if (loading) return;

    if (!user && !isPublic) {
      router.replace("/login");
    }

    // Si el usuario está autenticado en una ruta pública, redirigir al dashboard
    if (user && isPublic) {
      router.replace("/");
    }
  }, [user, loading, isPublic, router]);

  // Mostrar pantalla de carga mientras se verifica el token
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-600 border-t-transparent" />
          <p className="mt-3 text-sm text-slate-500">Verificando sesión...</p>
        </div>
      </div>
    );
  }

  // Si la ruta es pública y el usuario está autenticado, no renderizar nada
  // (la redirección ocurre en el useEffect)
  if (isPublic && user) {
    return null;
  }

  // Si no hay usuario y la ruta no es pública, no renderizar nada
  // (la redirección ocurre en el useEffect)
  if (!user && !isPublic) {
    return null;
  }

  return <>{children}</>;
}