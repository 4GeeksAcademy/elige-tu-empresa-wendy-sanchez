"use client";

import React, { useState } from "react";
import Link from "next/link";

/**
 * RagChat — Chat interface for the HealthCore RAG assistant.
 */

type Source = {
  source_document: string;
  section: string;
  score: number;
};

type RagResponse = {
  answer: string;
  sources: Source[];
  chunks_retrieved: number;
  score_threshold: number | null;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: boolean;
};

const SAMPLE_QUESTIONS: string[] = [
  "¿Qué seguros aceptan en las clínicas de Estados Unidos?",
  "¿Cobran cargo por no-show a pacientes de Medicare?",
  "¿Qué documentos necesito llevar a mi primera cita?",
  "¿Cuánto tiempo tarda una referencia interna a un especialista?",
];

const DOC_LABELS: Record<string, string> = {
  "insurance-coverage": "Cobertura de Seguros",
  "appointment-policy": "Política de Citas",
  "new-patient-checklist": "Checklist Pacientes Nuevos",
  "referral-process": "Proceso de Referencias",
};

function formatDocName(key: string): string {
  return DOC_LABELS[key] ?? key.replace(/-/g, " ");
}

function formatScore(score: number): string {
  const pct = Math.round(score * 100);
  if (pct >= 80) return `\uD83D\uDD35 ${pct}%`;
  if (pct >= 60) return `\uD83D\uDFE2 ${pct}%`;
  if (pct >= 40) return `\uD83D\uDFE1 ${pct}%`;
  return `\u26AA ${pct}%`;
}

function getApiBase(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return "http://localhost:8000";
    }
  }
  return "";
}

export default function RagChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSources, setShowSources] = useState(true);

  async function ask(question: string) {
    if (!question || loading) return null;
    setLoading(true);

    try {
      const apiBase = getApiBase();
      let data: RagResponse;

      if (apiBase) {
        const resp = await fetch(`${apiBase}/rag/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            top_k: 5,
            score_threshold: 0.3,
          }),
        });
        if (!resp.ok) throw new Error(`API returned ${resp.status}`);
        data = await resp.json();
      } else {
        const resp = await fetch("/api/rag/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        });
        if (!resp.ok) throw new Error(`API returned ${resp.status}`);
        data = await resp.json();
      }

      return {
        role: "assistant" as const,
        content: data.answer,
        sources: data.sources,
      };
    } catch (err) {
      console.error("RagChat error:", err);
      return {
        role: "assistant" as const,
        content:
          "Lo siento, no pude conectar con el asistente. " +
          "Verifica que el servidor RAG esté corriendo e intenta de nuevo.",
        error: true,
      };
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);

    const assistantMsg = await ask(question);
    if (assistantMsg) {
      setMessages((prev) => [...prev, assistantMsg]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleSampleClick(q: string) {
    if (loading) return;
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    const assistantMsg = await ask(q);
    if (assistantMsg) {
      setMessages((prev) => [...prev, assistantMsg]);
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8 sm:px-6">
      {/* Back link */}
      <Link
        href="/"
        className="text-sm text-indigo-600 hover:text-indigo-700"
      >
        ← Volver al sitio
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-gray-900">
        Asistente para Coordinadores
      </h1>
      <p className="mt-2 text-gray-600">
        Haz preguntas sobre cobertura de seguros, políticas de citas,
        referencias a especialistas y más. Las respuestas se basan en
        la base de conocimiento oficial de HealthCore.
      </p>

      {/* Messages */}
      <div className="mb-6 mt-6 space-y-4">
        {messages.length === 0 && (
          <div className="rounded-2xl border border-gray-200 bg-white p-8 text-center">
            <div className="text-5xl">🏥</div>
            <h2 className="mt-4 text-xl font-semibold text-gray-800">
              ¿En qué puedo ayudarte?
            </h2>
            <p className="mt-2 text-gray-600">
              Selecciona una pregunta de ejemplo o escribe tu propia consulta
              sobre las políticas y procedimientos de HealthCore.
            </p>
            <div className="mt-6 flex flex-wrap gap-3 justify-center">
              {SAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSampleClick(q)}
                  className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 hover:border-indigo-400"
                >
                  {q.length > 40 ? q.slice(0, 40) + "…" : q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-2xl p-4 ${
              msg.role === "user"
                ? "bg-indigo-50 border border-indigo-200 ml-4"
                : msg.error
                  ? "bg-red-50 border border-red-200"
                  : "bg-white border border-gray-200 mr-4"
            }`}
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {msg.role === "user" ? "Coordinador" : "HealthCore RAG"}
              {msg.error ? " (Error de conexión)" : ""}
            </p>
            <div className="mt-1.5 whitespace-pre-wrap text-gray-900">
              {msg.content}
            </div>

            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && showSources && (
              <details className="mt-3">
                <summary className="text-xs text-gray-400 cursor-pointer">
                  Fuentes ({msg.sources.length})
                </summary>
                <div className="mt-1 space-y-1">
                  {msg.sources.map((s, j) => (
                    <div
                      key={j}
                      className="flex items-center gap-2 text-xs text-gray-500"
                    >
                      <span>{formatScore(s.score)}</span>
                      <span className="font-medium">
                        {formatDocName(s.source_document)}
                      </span>
                      <span className="text-gray-400">— {s.section}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white p-4 mr-4">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
            <span className="text-sm text-gray-500">
              Consultando base de conocimiento...
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4">
        <div className="mx-auto max-w-4xl flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu pregunta sobre HealthCore..."
            disabled={loading}
            className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-base text-gray-900 placeholder-gray-400 shadow-inner focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-60"
          />
          <button
            onClick={handleSend}
            disabled={loading || input.trim().length < 3}
            className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
          >
            {loading ? "..." : "Enviar"}
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showSources}
              onChange={(e) => setShowSources(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600"
            />
            Mostrar fuentes
          </label>
          <span>
            API: <code className="text-indigo-600">/rag/query</code>
          </span>
        </div>
      </div>
    </div>
  );
}
