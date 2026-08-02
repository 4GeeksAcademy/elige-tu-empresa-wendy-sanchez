import type { Metadata } from "next";
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
