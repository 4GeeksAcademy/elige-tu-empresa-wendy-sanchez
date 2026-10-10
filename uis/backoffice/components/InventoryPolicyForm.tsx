"use client";

import { useState, type FormEvent } from "react";
import { captureStockSnapshot, downloadOrderHistory, reconcileStock, updateStockPolicy, type MedicalSupply } from "@/lib/inventoryApi";
import { useAuth } from "@/lib/AuthContext";

export default function InventoryPolicyForm({ supplies }: { supplies: MedicalSupply[] }) {
  const { user } = useAuth();
  const [product, setProduct] = useState("");
  const [clinic, setClinic] = useState("1");
  const [minimum, setMinimum] = useState("0");
  const [expiry, setExpiry] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [counted, setCounted] = useState("0");
  async function report(action: () => Promise<string>) {
    setBusy(true); setMessage(""); setFailed(false);
    try { setMessage(await action()); }
    catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "Operación no disponible."); }
    finally { setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage(""); setFailed(false);
    try {
      await updateStockPolicy(Number(product), { clinic_id: Number(clinic), minimum_quantity: Number(minimum), ...(expiry ? { expiry_date: expiry } : {}) });
      setMessage("Política de inventario guardada.");
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : "No se pudo guardar la política."); }
    finally { setBusy(false); }
  }
  return <section className="mt-8 border-t border-slate-200 pt-6">
    <h2 className="text-lg font-semibold">Política de inventario</h2>
    <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="grid gap-1 text-sm">Suministro<select aria-label="Suministro de política" value={product} onChange={(event) => setProduct(event.target.value)} required className="rounded-md border border-slate-300 p-2"><option value="">Selecciona un suministro</option>{supplies.map((supply) => <option key={supply.id} value={supply.id}>{supply.name}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Clínica<select value={clinic} onChange={(event) => setClinic(event.target.value)} className="rounded-md border border-slate-300 p-2">{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>Clínica {index + 1} ({index < 9 ? "US" : "UK"})</option>)}</select></label>
      <label className="grid gap-1 text-sm">Mínimo de unidades<input type="number" min="0" step="1" value={minimum} onChange={(event) => setMinimum(event.target.value)} required className="rounded-md border border-slate-300 p-2" /></label>
      <label className="grid gap-1 text-sm">Caducidad del suministro<input type="date" value={expiry} onChange={(event) => setExpiry(event.target.value)} className="rounded-md border border-slate-300 p-2" /></label>
      <button disabled={busy} className="rounded-md bg-cyan-700 px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Guardando..." : "Guardar política"}</button>
    </form>
    <div className="mt-4 flex flex-wrap items-end gap-3">
      <button type="button" disabled={busy} onClick={() => void report(async () => { const result = await captureStockSnapshot(); return `Saldos capturados: ${result.captured}.`; })} className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">Capturar saldos</button>
      <button type="button" disabled={busy} onClick={() => void report(async () => { await downloadOrderHistory(); return "Historial exportado."; })} className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">Exportar historial CSV</button>
      {user?.role === "admin" && <>
        <label className="grid gap-1 text-sm">Recuento físico<input type="number" min="0" step="1" value={counted} onChange={(event) => setCounted(event.target.value)} className="w-32 rounded-md border border-slate-300 p-2" /></label>
        <button type="button" disabled={busy || !product || !Number.isInteger(Number(counted)) || Number(counted) < 0} onClick={() => void report(async () => { const result = await reconcileStock(Number(product), Number(clinic), Number(counted)); return `Diferencia de conciliación: ${result.variance_quantity}.`; })} className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">Conciliar existencias</button>
      </>}
    </div>
    {message && <p role={failed ? "alert" : "status"} className={`mt-3 text-sm ${failed ? "text-red-700" : "text-green-700"}`}>{message}</p>}
  </section>;
}