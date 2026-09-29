"use client";

interface LoadingSpinnerProps {
  /** Mensaje que se muestra junto al spinner */
  message?: string;
  /** Clases adicionales para el contenedor exterior */
  className?: string;
  /** Si es true, ocupa pantalla completa con padding (por defecto true) */
  fullPage?: boolean;
  /** Tamaño del spinner: sm | md | lg */
  size?: "sm" | "md" | "lg";
}

const SIZE_CLASSES = {
  sm: "h-5 w-5 border-2",
  md: "h-8 w-8 border-4",
  lg: "h-12 w-12 border-4",
} as const;

// ══════════════════════════════════════════════════════════════════════════════
//  LoadingSpinner — Indicador de carga reutilizable
// ══════════════════════════════════════════════════════════════════════════════
//  Soportes:
//   • fullPage  → contenedor con padding y centrado vertical
//   • inline    → sin contenedor, solo spinner + texto (útil para listas)
//   • size      → sm / md / lg
// ══════════════════════════════════════════════════════════════════════════════

export default function LoadingSpinner({
  message,
  className = "",
  fullPage = true,
  size = "md",
}: LoadingSpinnerProps) {
  const spinner = (
    <div className={`flex items-center gap-3 text-slate-500 ${className}`}>
      <div
        className={`animate-spin rounded-full border-sky-600 border-t-transparent ${SIZE_CLASSES[size]}`}
      />
      {message && <p className="text-sm">{message}</p>}
    </div>
  );

  if (!fullPage) return spinner;

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex items-center justify-center py-20">{spinner}</div>
    </main>
  );
}