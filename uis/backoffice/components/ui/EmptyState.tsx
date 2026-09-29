"use client";
import type { ReactNode } from "react";

interface EmptyStateProps {
  /** Mensaje principal indicando que no hay datos */
  message: string;
  /** Descripción opcional más detallada */
  description?: string;
  /** Clases adicionales */
  className?: string;
  /** Icono o elemento decorativo opcional */
  icon?: ReactNode;
  /** Acción opcional (botón / link) */
  action?: ReactNode;
  /** Si es true, ocupa pantalla completa (por defecto false) */
  fullPage?: boolean;
}

// ══════════════════════════════════════════════════════════════════════════════
//  EmptyState — Estado vacío reutilizable
// ══════════════════════════════════════════════════════════════════════════════
//  Muestra un mensaje cuando no hay datos que renderizar.
//  Soportes:
//   • icon     → elemento decorativo (svg, emoji, etc.)
//   • action   → botón o link para realizar una acción
//   • fullPage → contenedor con padding
// ══════════════════════════════════════════════════════════════════════════════

export default function EmptyState({
  message,
  description,
  className = "",
  icon,
  action,
  fullPage = false,
}: EmptyStateProps) {
  const content = (
    <div
      className={`px-4 py-12 text-center ${fullPage ? "rounded-xl border border-slate-200 bg-white" : ""} ${className}`}
    >
      {icon && <div className="mb-3 flex justify-center">{icon}</div>}
      <p className="text-sm text-slate-500">{message}</p>
      {description && (
        <p className="mt-1 text-xs text-slate-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );

  if (!fullPage) return content;

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      {content}
    </main>
  );
}