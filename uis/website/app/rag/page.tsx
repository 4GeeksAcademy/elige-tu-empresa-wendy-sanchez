import type { Metadata } from "next";
import RagChat from "@/components/RagChat";

export const metadata: Metadata = {
  title: "HealthCore | RAG — Asistente para Coordinadores",
  description:
    "Asistente de preguntas y respuestas basado en la base de conocimiento de HealthCore para coordinadores de pacientes.",
};

export default function RagPage() {
  return (
    <>
      <RagChat />
    </>
  );
}