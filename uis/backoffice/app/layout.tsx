import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthCore Backoffice",
  description: "Internal operations dashboard for HealthCore teams.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen bg-slate-100">
          <header className="border-b border-slate-200 bg-slate-950 text-slate-50">
            <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
                  Internal App
                </p>
                <h1 className="text-lg font-semibold">HealthCore Backoffice</h1>
                <nav className="mt-2 flex gap-3 text-xs text-slate-300">
                  <Link className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white" href="/">
                    Dashboard
                  </Link>
                  <Link
                    className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white"
                    href="/incidents"
                  >
                    Incident Analysis
                  </Link>
                  <Link
                    className="rounded px-2 py-1 hover:bg-slate-800 hover:text-white"
                    href="/suppliers"
                  >
                    Supplier Directory
                  </Link>
                </nav>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
                Dashboard Preview
              </span>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
