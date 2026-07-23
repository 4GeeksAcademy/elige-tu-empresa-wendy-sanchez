"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import CandidateForm from "@/components/CandidateForm";
import { getStageLabel, getStatusLabel, STAGE_OPTIONS, STATUS_OPTIONS } from "@/lib/domain";
import { createRecord, getRecords } from "@/services/api";
import { CandidateCreatePayload, CandidateRecord } from "@/types/candidate";

export default function Home() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [records, setRecords] = useState<CandidateRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createFeedback, setCreateFeedback] = useState<string | null>(null);

  const statusValue = searchParams.get("status") ?? "";
  const stageValue = searchParams.get("stage") ?? "";
  const searchValue = searchParams.get("search") ?? "";

  const detailContext = useMemo(() => searchParams.toString(), [searchParams]);

  const setQueryParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams.toString());

      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }

      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const loadRecords = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getRecords({
        status: statusValue || undefined,
        stage: stageValue || undefined,
        search: searchValue || undefined,
      });
      setRecords(response.data);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "No se pudo cargar el listado.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [searchValue, stageValue, statusValue]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);
  /* eslint-enable react-hooks/set-state-in-effect */

  async function handleCreate(payload: CandidateCreatePayload) {
    await createRecord(payload);
    setCreateFeedback("Candidatura creada correctamente.");
    await loadRecords();
  }

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 md:px-8">
      <header className="rounded-3xl border border-sky-200 bg-gradient-to-r from-cyan-100 via-sky-50 to-indigo-100 p-6 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-sky-800">HealthCore Digital</p>
        <h1 className="mt-2 text-4xl font-bold text-slate-900">Talent Pipeline Tracker</h1>
        <p className="mt-2 max-w-3xl text-slate-700">
          Gestiona candidaturas para People con filtros por estado y etapa, búsqueda sin recargas y acceso directo al detalle del candidato.
        </p>
      </header>

      <section className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-900">Filtros y búsqueda</h2>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Estado</span>
            <select
              value={statusValue}
              onChange={(event) => setQueryParam("status", event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            >
              <option value="">Todos</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Etapa</span>
            <select
              value={stageValue}
              onChange={(event) => setQueryParam("stage", event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            >
              <option value="">Todas</option>
              {STAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1">
            <span className="text-sm font-medium text-slate-700">Buscar por nombre o email</span>
            <input
              value={searchValue}
              onChange={(event) => setQueryParam("search", event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
              placeholder="Ej: maria o maria@email.com"
            />
          </label>
        </div>
      </section>

      <section className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">Listado de candidaturas</h2>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
            {records.length} resultados
          </span>
        </div>

        {loading ? <p className="text-slate-700">Cargando candidaturas...</p> : null}
        {!loading && error ? (
          <p className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800">{error}</p>
        ) : null}
        {!loading && !error && records.length === 0 ? (
          <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
            No hay candidaturas para los filtros actuales.
          </p>
        ) : null}

        {!loading && !error && records.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] border-separate border-spacing-y-2 text-left text-sm">
              <thead>
                <tr className="text-slate-500">
                  <th className="px-3 py-2">Nombre</th>
                  <th className="px-3 py-2">Puesto</th>
                  <th className="px-3 py-2">Estado</th>
                  <th className="px-3 py-2">Etapa</th>
                  <th className="px-3 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => {
                  const href = detailContext
                    ? `/candidates/${record.id}?from=${encodeURIComponent(detailContext)}`
                    : `/candidates/${record.id}`;

                  return (
                    <tr key={record.id} className="rounded-xl bg-white shadow-sm">
                      <td className="px-3 py-3 font-medium text-slate-900">{record.full_name}</td>
                      <td className="px-3 py-3 text-slate-700">{record.position}</td>
                      <td className="px-3 py-3 text-slate-700">{getStatusLabel(record.status)}</td>
                      <td className="px-3 py-3 text-slate-700">{getStageLabel(record.stage)}</td>
                      <td className="px-3 py-3">
                        <Link href={href} className="font-semibold text-sky-700 hover:text-sky-900">
                          Ver detalle
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <CandidateForm
        title="Registrar nueva candidatura"
        submitLabel="Crear candidatura"
        successMessage="Candidatura registrada correctamente."
        onSubmit={handleCreate}
      />

      {createFeedback ? <p className="text-sm font-semibold text-emerald-700">{createFeedback}</p> : null}
    </main>
  );
}
