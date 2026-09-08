"use client";

import { AuthProvider } from "@/lib/AuthContext";
import AuthGuard from "@/components/AuthGuard";
import TrackerHeader from "@/components/TrackerHeader";

interface AuthShellProps {
  children: React.ReactNode;
}

export default function AuthShell({ children }: AuthShellProps) {
  return (
    <AuthProvider>
      <TrackerHeader />
      <AuthGuard>{children}</AuthGuard>
    </AuthProvider>
  );
}