"use client";

import React, { useState } from "react";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";

/**
 * KnowledgePanel — Q&A interface for the HealthCore knowledge base.
 *
 * Connects to POST /knowledge/query and displays the model's answer.
 * Handles loading, error, and empty states with proper UX feedback.
 */

const SAMPLE_QUESTIONS: string[] = [
  "¿Qué seguros aceptan en las clínicas de Estados Unidos?",
  "¿Cobran cargo por no-show a pacientes de Medicare?",
  "¿Qué documentos necesito llevar a mi primera cita?",
  "¿Cuánto tiempo tarda una referencia interna a un especialista?",
];

type Message = {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
};

function getApiBase(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    // When running locally, the backoffice dev server proxies API calls
    // via Next.js rewrites.  For direct backend access use the env var.
    if (host === "localhost" || host === "127.0.0.1") {
      return process.env.NEXT_PUBLIC_API_BASE ?? "";
    }
  }
  return "";
}

export default function KnowledgePanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function ask(question: string): Promise<Message | null> {
    if (!question || loading) return null;
    setLoading(true);

    try {
      const apiBase = getApiBase();
      let data: { answer: string };

      if (apiBase) {
        const resp = await fetch(`${apiBase}/knowledge/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        });
        if (!resp.ok) throw new Error(`API returned ${resp.status}`);
        data = await resp.json();
      } else {
        // Use Next.js rewrite proxy — same origin
        const resp = await fetch("/api/knowledge/query", {
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
      };
    } catch (err) {
      console.error("KnowledgePanel error:", err);
      return {
        role: "assistant" as const,
        content:
          "Lo siento, no pude conectar con la base de conocimiento. " +
          "Verifica que el servidor esté corriendo e intenta de nuevo.",
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

  function handleRetry() {
    // Re-send the last user question
    const lastUserIdx = messages
      .map((m, i) => ({ role: m.role, index: i }))
      .filter((m) => m.role === "user")
      .pop()?.index;
    if (lastUserIdx !== undefined) {
      const lastQuestion = messages[lastUserIdx].content;
      // Remove the failed assistant message
      setMessages(messages.slice(0, lastUserIdx + 1));
      handleSampleClick(lastQuestion);
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8 sm:px-6">
      {/* Header */}
      <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">
        Asistente de Conocimiento
      </h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        Haz preguntas sobre cobertura de seguros, políticas de citas,
        referencias a especialistas y más. Las respuestas se basan en
        la base de conocimiento oficial de HealthCore.
      </p>

      {/* Messages area */}
      <div className="mb-6 mt-6 space-y-4">
        {/* Empty state */}
        {messages.length === 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-800">
            <div className="text-5xl">🏥</div>
            <h2 className="mt-4 text-xl font-semibold text-slate-800 dark:text-slate-200">
              ¿En qué puedo ayudarte?
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Selecciona una pregunta de ejemplo o escribe tu propia consulta
              sobre las políticas y procedimientos de HealthCore.
            </p>
            <div className="mt-6 flex flex-wrap gap-3 justify-center">
              {SAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSampleClick(q)}
                  className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 hover:border-indigo-400 dark:border-indigo-600 dark:bg-indigo-950 dark:text-indigo-300 dark:hover:bg-indigo-900"
                >
                  {q.length > 40 ? q.slice(0, 40) + "\u2026" : q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-2xl p-4 ${
              msg.role === "user"
                ? "bg-indigo-50 border border-indigo-200 ml-4 dark:bg-indigo-950 dark:border-indigo-700"
                : msg.error
                  ? "bg-red-50 border border-red-200 mr-4 dark:bg-red-950 dark:border-red-700"
                  : "bg-white border border-slate-200 mr-4 dark:bg-slate-800 dark:border-slate-700"
            }`}
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {msg.role === "user" ? "Tú" : msg.error ? "Error" : "Asistente"}
            </p>
            <div className="mt-2 whitespace-pre-wrap text-slate-800 dark:text-slate-200">
              {msg.content}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <LoadingSpinner
            message="Consultando la base de conocimiento..."
            fullPage={false}
            size="sm"
          />
        )}

        {/* Retry button when last message is an error */}
        {messages.length > 0 && messages[messages.length - 1].error && !loading && (
          <div className="flex justify-center">
            <button
              onClick={handleRetry}
              className="rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Reintentar
            </button>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="sticky bottom-0 border-t border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu pregunta sobre HealthCore..."
            disabled={loading}
            className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm
              placeholder-slate-400 shadow-sm
              focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500
              dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200
              dark:placeholder-slate-500
              disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white
              hover:bg-indigo-700
              disabled:cursor-not-allowed disabled:opacity-60
              dark:bg-indigo-500 dark:hover:bg-indigo-400"
          >
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}