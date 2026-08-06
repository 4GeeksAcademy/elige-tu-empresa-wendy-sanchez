import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthCore | Outpatient Healthcare Services",
  description:
    "HealthCore is an outpatient healthcare network with 12 clinics across the US and UK, offering same-day appointments, extended hours, and bilingual care.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
