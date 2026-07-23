"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import CandidateForm from "@/components/CandidateForm";
import { getStageLabel, getStatusLabel, STAGE_OPTIONS, STATUS_OPTIONS } from "@/lib/domain";
import { validateNoteContent } from "@/lib/validation";
import {
  addNote,
  deleteNote,
  getNotes,
  getRecordById,
  patchRecord,
  replaceRecord,
} from "@/services/api";
import { CandidateCreatePayload, CandidateNote, CandidateRecord } from "@/types/candidate";

interface CandidateDetailClientProps {
  candidateId: string;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("es-ES", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function CandidateDetailClient({ candidateId }: CandidateDetailClientProps) {
  const searchParams = useSearchParams();
  const [candidate, setCandidate] = useState<CandidateRecord | null>(null);
  const [loadingCandidate, setLoadingCandidate] = useState(true);
  const [candidateError, setCandidateError] = useState<string | null>(null);

  const [notes, setNotes] = useState<CandidateNote[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(true);
  const [notesError, setNotesError] = useState<string | null>(null);

  const [statusUpdateMessage, setStatusUpdateMessage] = useState<string | null>(null);
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const [stageUpdateMessage, setStageUpdateMessage] = useState<string | null>(null);
  const [stageUpdateError, setStageUpdateError] = useState<string | null>(null);
  const [updatingStage, setUpdatingStage] = useState(false);

  const [newNote, setNewNote] = useState("");
  const [noteMessage, setNoteMessage] = useState<string | null>(null);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [savingNote, setSavingNote] = useState(false);

  const [deletingNoteId, setDeletingNoteId] = useState<string | null>(null);

  const fromQuery = searchParams.get("from");
  const backHref = useMemo(() => {
    if (!fromQuery) return "/";
    return `/?${fromQuery}`;
  }, [fromQuery]);

  const loadCandidate = useCallback(async () => {
    try {
      setLoadingCandidate(true);
      setCandidateError(null);
      const data = await getRecordById(candidateId);
      setCandidate(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo cargar la candidatura.";
      setCandidateError(message);
    } finally {
      setLoadingCandidate(false);
    }
  }, [candidateId]);

  const loadNotes = useCallback(async () => {
    try {
      setLoadingNotes(true);
      setNotesError(null);
      const response = await getNotes(candidateId);
      setNotes(response.data);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudieron cargar las notas.";
      setNotesError(message);
    } finally {
      setLoadingNotes(false);
    }
  }, [candidateId]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    void loadCandidate();
    void loadNotes();
  }, [loadCandidate, loadNotes]);
  /* eslint-enable react-hooks/set-state-in-effect */

  async function handleStatusChange(value: string) {
    if (!candidate) return;

    try {
      setUpdatingStatus(true);
      setStatusUpdateError(null);
      setStatusUpdateMessage(null);
      const updated = await patchRecord(candidate.id, { status: value as CandidateRecord["status"] });
      setCandidate(updated);
      setStatusUpdateMessage("Estado actualizado correctamente.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo actualizar el estado.";
      setStatusUpdateError(message);
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleStageChange(value: string) {
    if (!candidate) return;

    try {
      setUpdatingStage(true);
      setStageUpdateError(null);
      setStageUpdateMessage(null);
      const updated = await patchRecord(candidate.id, { stage: value as CandidateRecord["stage"] });
      setCandidate(updated);
      setStageUpdateMessage("Etapa actualizada correctamente.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo actualizar la etapa.";
      setStageUpdateError(message);
    } finally {
      setUpdatingStage(false);
    }
  }

  async function handleAddNote(event: globalThis.React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationError = validateNoteContent(newNote);
    if (validationError) {
      setNoteError(validationError);
      setNoteMessage(null);
      return;
    }

    if (!candidate) return;

    try {
      setSavingNote(true);
      setNoteError(null);
      setNoteMessage(null);
      await addNote(candidate.id, { content: newNote.trim() });
      setNewNote("");
      setNoteMessage("Nota agregada correctamente.");
      await loadNotes();
      await loadCandidate();
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo agregar la nota.";
      setNoteError(message);
    } finally {
      setSavingNote(false);
    }
  }

  async function handleDeleteNote(noteId: string) {
    if (!candidate) return;

    try {
      setDeletingNoteId(noteId);
      setNoteError(null);
      setNoteMessage(null);
      await deleteNote(candidate.id, noteId);
      setNoteMessage("Nota eliminada correctamente.");
      await loadNotes();
      await loadCandidate();
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo eliminar la nota.";
      setNoteError(message);
    } finally {
      setDeletingNoteId(null);
    }
  }

  async function handleReplace(payload: CandidateCreatePayload) {
    if (!candidate) return;

    const updated = await replaceRecord(candidate.id, payload);
    setCandidate(updated);
  }

  if (loadingCandidate) {
    return <p className="p-6 text-slate-700">Cargando detalle de candidatura...</p>;
  }

  if (candidateError) {
    return (
      <div className="p-6">
        <p className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800">{candidateError}</p>
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="p-6">
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
          No se encontró la candidatura solicitada.
        </p>
      </div>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="rounded-2xl border border-sky-100 bg-white/85 p-6 shadow-sm">
        <Link href={backHref} className="text-sm font-semibold text-sky-700 hover:text-sky-900">
          Volver al listado
        </Link>

        <h1 className="mt-2 text-3xl font-bold text-slate-900">{candidate.full_name}</h1>
        <p className="mt-1 text-slate-700">{candidate.position}</p>

        <div className="mt-5 grid gap-3 text-sm text-slate-700 md:grid-cols-2">
          <p>
            <strong>Email:</strong> {candidate.email}
          </p>
          <p>
            <strong>Teléfono:</strong> {candidate.phone}
          </p>
          <p>
            <strong>LinkedIn:</strong>{" "}
            {candidate.linkedin_url ? (
              <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sky-700 underline">
                Ver perfil
              </a>
            ) : (
              "No disponible"
            )}
          </p>
          <p>
            <strong>CV:</strong>{" "}
            {candidate.cv_url ? (
              <a href={candidate.cv_url} target="_blank" rel="noopener noreferrer" className="text-sky-700 underline">
                Ver CV
              </a>
            ) : (
              "No disponible"
            )}
          </p>
          <p>
            <strong>Años de experiencia:</strong> {candidate.experience_years}
          </p>
          <p>
            <strong>Fecha de aplicación:</strong> {formatDate(candidate.applied_at)}
          </p>
          <p>
            <strong>Estado actual:</strong> {getStatusLabel(candidate.status)}
          </p>
          <p>
            <strong>Etapa actual:</strong> {getStageLabel(candidate.stage)}
          </p>
        </div>
      </header>

      <section className="grid gap-6 md:grid-cols-2">
        <article className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-900">Actualizar estado</h2>
          <select
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={candidate.status}
            disabled={updatingStatus}
            onChange={(event) => void handleStatusChange(event.target.value)}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {statusUpdateMessage ? <p className="mt-2 text-sm text-emerald-700">{statusUpdateMessage}</p> : null}
          {statusUpdateError ? <p className="mt-2 text-sm text-red-700">{statusUpdateError}</p> : null}
        </article>

        <article className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-900">Actualizar etapa</h2>
          <select
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={candidate.stage}
            disabled={updatingStage}
            onChange={(event) => void handleStageChange(event.target.value)}
          >
            {STAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {stageUpdateMessage ? <p className="mt-2 text-sm text-emerald-700">{stageUpdateMessage}</p> : null}
          {stageUpdateError ? <p className="mt-2 text-sm text-red-700">{stageUpdateError}</p> : null}
        </article>
      </section>

      <CandidateForm
        key={candidate.updated_at}
        title="Editar candidatura"
        submitLabel="Guardar cambios"
        successMessage="Candidatura actualizada correctamente."
        initialValues={{
          full_name: candidate.full_name,
          email: candidate.email,
          phone: candidate.phone,
          position: candidate.position,
          linkedin_url: candidate.linkedin_url ?? "",
          cv_url: candidate.cv_url ?? "",
          experience_years: String(candidate.experience_years),
        }}
        onSubmit={handleReplace}
      />

      <section className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-900">Notas internas</h2>

        <form className="mt-4 flex flex-col gap-3" onSubmit={(event) => void handleAddNote(event)}>
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Nueva nota</span>
            <textarea
              className="min-h-28 rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
              value={newNote}
              onChange={(event) => {
                setNewNote(event.target.value);
                setNoteError(null);
              }}
              placeholder="Agrega aquí una observación de entrevista o llamada..."
            />
          </label>
          <button
            type="submit"
            disabled={savingNote}
            className="w-fit rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {savingNote ? "Guardando nota..." : "Agregar nota"}
          </button>
        </form>

        {noteMessage ? <p className="mt-3 text-sm font-medium text-emerald-700">{noteMessage}</p> : null}
        {noteError ? <p className="mt-3 text-sm font-medium text-red-700">{noteError}</p> : null}

        <div className="mt-5">
          {loadingNotes ? <p className="text-slate-700">Cargando notas...</p> : null}
          {!loadingNotes && notesError ? (
            <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">{notesError}</p>
          ) : null}
          {!loadingNotes && !notesError && notes.length === 0 ? (
            <p className="text-slate-600">Esta candidatura aún no tiene notas.</p>
          ) : null}

          {!loadingNotes && !notesError && notes.length > 0 ? (
            <ul className="grid gap-3">
              {notes.map((note) => (
                <li key={note.id} className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-slate-800">{note.content}</p>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-600">
                    <span>{formatDate(note.created_at)}</span>
                    <button
                      type="button"
                      onClick={() => void handleDeleteNote(note.id)}
                      disabled={deletingNoteId === note.id}
                      className="font-semibold text-red-700 hover:text-red-900 disabled:opacity-60"
                    >
                      {deletingNoteId === note.id ? "Eliminando..." : "Eliminar"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>
    </main>
  );
}
