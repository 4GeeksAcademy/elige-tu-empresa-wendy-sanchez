"use client";

interface ErrorMessageProps {
  /** Título del error (ej: "Error de conexión") */
  title?: string;
  /** Mensaje descriptivo del error */
  message?: string;
  /** Callback opcional para botón "Reintentar" */
  onRetry?: () => void;
  /** Texto personalizado para el botón de reintentar */
  retryLabel?: string;
  /** Clases adicionales para el contenedor */
  className?: string;
  /** Si es true, ocupa pantalla completa (por defecto true) */
  fullPage?: boolean;
  /** Variante visual: error | warning | info */
  variant?: "error" | "warning" | "info";
}

// ══════════════════════════════════════════════════════════════════════════════
//  ErrorMessage — Bloque de error reutilizable
// ══════════════════════════════════════════════════════════════════════════════
//  Soportes:
//   • fullPage  → contenedor con padding
//   • onRetry   → callback para botón "Reintentar"
//   • variant   → error (rojo), warning (ámbar), info (azul)
// ══════════════════════════════════════════════════════════════════════════════

const VARIANT_STYLES = {
  error: {
    container: "border-red-200 bg-red-50",
    title: "text-red-800",
    message: "text-red-600",
    button: "bg-red-600 hover:bg-red-700 text-white",
  },
  warning: {
    container: "border-amber-200 bg-amber-50",
    title: "text-amber-800",
    message: "text-amber-600",
    button: "bg-amber-600 hover:bg-amber-700 text-white",
  },
  info: {
    container: "border-blue-200 bg-blue-50",
    title: "text-blue-800",
    message: "text-blue-600",
    button: "bg-blue-600 hover:bg-blue-700 text-white",
  },
} as const;

export default function ErrorMessage({
  title,
  message,
  onRetry,
  retryLabel = "Reintentar",
  className = "",
  fullPage = true,
  variant = "error",
}: ErrorMessageProps) {
  const styles = VARIANT_STYLES[variant];

  const content = (
    <div
      className={`rounded-xl border p-4 sm:p-6 ${styles.container} ${className}`}
    >
      {title && (
        <p className={`text-sm font-medium ${styles.title}`}>{title}</p>
      )}
      {message && (
        <p className={`mt-1 text-sm ${styles.message}`}>{message}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className={`mt-4 rounded-lg px-4 py-2 text-sm ${styles.button}`}
        >
          {retryLabel}
        </button>
      )}
    </div>
  );

  if (!fullPage) return content;

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      {content}
    </main>
  );
}