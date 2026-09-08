import type { Metadata } from "next";
import "./globals.css";
import AuthShell from "./AuthShell";

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
        <AuthShell>{children}</AuthShell>
      </body>
    </html>
  );
}
