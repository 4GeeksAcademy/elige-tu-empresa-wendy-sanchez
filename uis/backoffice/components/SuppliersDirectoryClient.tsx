"use client";

import { useCallback, useMemo, useState } from "react";

import {
  archiveSupplier,
  createSupplier,
  fetchSuppliers,
  updateSupplierRate,
  updateSupplierStatus,
} from "../lib/suppliersApi";
import {
  CATEGORY_LABELS,
  COMPLIANCE_AGREEMENTS,
  CURRENCY_BY_COUNTRY,
  SUPPLIER_CATEGORIES,
  SUPPLIER_COUNTRIES,
  type ComplianceAgreement,
  type Supplier,
  type SupplierCategory,
  type SupplierCountry,
  type SupplierStatus,
} from "../types/supplier";

interface SupplierFormState {
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthlyRate: string;
  complianceAgreement: ComplianceAgreement | "";
  contractRenewalDate: string;
  contactEmail: string;
  notes: string;
}

const EMPTY_FORM: SupplierFormState = {
  name: "",
  country: "USA",
  categories: [],
  monthlyRate: "",
  complianceAgreement: "",
  contractRenewalDate: "",
  contactEmail: "",
  notes: "",
};

const formatRate = (supplier: Supplier): string =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: supplier.currency,
    maximumFractionDigits: 2,
  }).format(supplier.monthly_rate);

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("es-ES");
};

type FieldErrors = Partial<Record<"name" | "monthlyRate" | "categories" | "contactEmail", string>>;

const validateForm = (form: SupplierFormState): FieldErrors => {
  const errors: FieldErrors = {};

  if (form.name.trim().length < 2) {
    errors.name = "El nombre comercial debe tener al menos 2 caracteres";
  }

  const rate = Number(form.monthlyRate);
  if (form.monthlyRate.trim() === "") {
    errors.monthlyRate = "Indica la tarifa mensual del contrato";
  } else if (!Number.isFinite(rate) || rate <= 0) {
    errors.monthlyRate = "La tarifa mensual debe ser un número mayor que cero";
  }

  if (form.categories.length === 0) {
    errors.categories = "Selecciona al menos una categoría de producto o servicio";
  }

  if (form.contactEmail.trim() !== "" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.contactEmail.trim())) {
    errors.contactEmail = "Introduce un email válido (ejemplo: nombre@proveedor.com)";
  }

  return errors;
};

export default function SuppliersDirectoryClient({
  initialSuppliers,
  initialError,
}: {
  initialSuppliers: Supplier[];
  initialError: string | null;
}) {
  const [suppliers, setSuppliers] = useState<Supplier[]>(initialSuppliers);
  const [isLoading, setIsLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(initialError);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [countryFilter, setCountryFilter] = useState<SupplierCountry | "">("");
  const [categoryFilter, setCategoryFilter] = useState<SupplierCategory | "">("");

  const [form, setForm] = useState<SupplierFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [rateDrafts, setRateDrafts] = useState<Record<number, string>>({});
  const [rowBusyId, setRowBusyId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const loadSuppliers = useCallback(
    async (country: SupplierCountry | "", category: SupplierCategory | "") => {
      setIsLoading(true);
      try {
        const data = await fetchSuppliers({ country, category });
        setSuppliers(data);
        setListError(null);
      } catch (error) {
        setListError(error instanceof Error ? error.message : "No se pudo cargar el directorio");
        setSuppliers([]);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const applyFilters = (country: SupplierCountry | "", category: SupplierCategory | "") => {
    setCountryFilter(country);
    setCategoryFilter(category);
    void loadSuppliers(country, category);
  };

  const activeCount = useMemo(
    () => suppliers.filter((supplier) => supplier.status === "active").length,
    [suppliers],
  );

  const archivedCount = useMemo(
    () => suppliers.filter((supplier) => supplier.archived_at !== null).length,
    [suppliers],
  );

  const replaceSupplier = (updated: Supplier) => {
    setSuppliers((current) =>
      current.map((supplier) => (supplier.id === updated.id ? updated : supplier)),
    );
  };

  const toggleFormCategory = (category: SupplierCategory) => {
    setForm((current) => ({
      ...current,
      categories: current.categories.includes(category)
        ? current.categories.filter((item) => item !== category)
        : [...current.categories, category],
    }));
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setFeedback(null);

    const errors = validateForm(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setFormError("Revisa los campos marcados antes de registrar el proveedor.");
      return;
    }

    setIsSubmitting(true);

    try {
      const created = await createSupplier({
        name: form.name.trim(),
        country: form.country,
        categories: form.categories,
        monthly_rate: Number(form.monthlyRate),
        currency: CURRENCY_BY_COUNTRY[form.country],
        status: "active",
        compliance_agreement: form.complianceAgreement || null,
        contract_renewal_date: form.contractRenewalDate || null,
        contact_email: form.contactEmail.trim() || null,
        notes: form.notes.trim() || null,
      });

      setForm(EMPTY_FORM);
      setFieldErrors({});
      setFeedback(`Proveedor "${created.name}" registrado con id ${created.id}.`);
      await loadSuppliers(countryFilter, categoryFilter);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "No se pudo registrar el proveedor");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRateUpdate = async (supplier: Supplier) => {
    const draft = rateDrafts[supplier.id];
    setRowError(null);
    setFeedback(null);

    const nextRate = Number(draft);
    if (!Number.isFinite(nextRate) || nextRate <= 0) {
      setRowError(`La tarifa de ${supplier.name} debe ser un número mayor que cero`);
      return;
    }

    setRowBusyId(supplier.id);

    try {
      const updated = await updateSupplierRate(supplier.id, nextRate);
      replaceSupplier(updated);
      setRateDrafts((current) => {
        const next = { ...current };
        delete next[supplier.id];
        return next;
      });
      setFeedback(
        `Tarifa de ${updated.name} actualizada a ${formatRate(updated)} (${formatTimestamp(updated.updated_at)}).`,
      );
    } catch (error) {
      setRowError(error instanceof Error ? error.message : "No se pudo actualizar la tarifa");
    } finally {
      setRowBusyId(null);
    }
  };

  const handleStatusToggle = async (supplier: Supplier) => {
    const nextStatus: SupplierStatus = supplier.status === "active" ? "suspended" : "active";
    setRowError(null);
    setFeedback(null);
    setRowBusyId(supplier.id);

    try {
      const updated = await updateSupplierStatus(supplier.id, nextStatus);
      replaceSupplier(updated);
      setFeedback(
        `${updated.name} ahora está ${updated.status === "active" ? "activo" : "suspendido"}.`,
      );
    } catch (error) {
      setRowError(error instanceof Error ? error.message : "No se pudo cambiar el estado");
    } finally {
      setRowBusyId(null);
    }
  };

  const handleArchive = async (supplier: Supplier) => {
    setRowError(null);
    setFeedback(null);
    setRowBusyId(supplier.id);

    try {
      const updated = await archiveSupplier(supplier.id);
      replaceSupplier(updated);
      setFeedback(
        `${updated.name} se eliminó del directorio activo. El registro se conserva con su fecha de baja para auditorías.`,
      );
    } catch (error) {
      setRowError(error instanceof Error ? error.message : "No se pudo eliminar el proveedor");
    } finally {
      setRowBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <section
        aria-labelledby="filters-heading"
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3 id="filters-heading" className="text-lg font-semibold text-slate-900">
          Filtros
        </h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="block text-sm font-medium text-slate-700" htmlFor="country-filter">
              País del contrato
            </label>
            <select
              id="country-filter"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              value={countryFilter}
              onChange={(event) =>
                applyFilters(event.target.value as SupplierCountry | "", categoryFilter)
              }
            >
              <option value="">Todos los países</option>
              {SUPPLIER_COUNTRIES.map((country) => (
                <option key={country} value={country}>
                  {country}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700" htmlFor="category-filter">
              Categoría
            </label>
            <select
              id="category-filter"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              value={categoryFilter}
              onChange={(event) =>
                applyFilters(countryFilter, event.target.value as SupplierCategory | "")
              }
            >
              <option value="">Todas las categorías</option>
              {SUPPLIER_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              onClick={() => applyFilters("", "")}
            >
              Limpiar filtros
            </button>
          </div>
        </div>

        <p className="mt-4 text-sm text-slate-600" aria-live="polite">
          {isLoading
            ? "Cargando proveedores…"
            : `${suppliers.length} proveedores · ${activeCount} activos · ${suppliers.length - activeCount - archivedCount} suspendidos · ${archivedCount} eliminados`}
        </p>
      </section>

      <section
        aria-labelledby="directory-heading"
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3 id="directory-heading" className="text-lg font-semibold text-slate-900">
          Directorio de proveedores
        </h3>

        <div aria-live="polite" className="mt-2 space-y-2">
          {listError ? (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {listError}
            </p>
          ) : null}
          {rowError ? (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {rowError}
            </p>
          ) : null}
          {feedback ? (
            <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{feedback}</p>
          ) : null}
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left text-sm">
            <caption className="sr-only">
              Proveedores de HealthCore con país, categorías, tarifa mensual y estado
            </caption>
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-3 py-2">Proveedor</th>
                <th scope="col" className="px-3 py-2">País</th>
                <th scope="col" className="px-3 py-2">Categorías</th>
                <th scope="col" className="px-3 py-2">Tarifa mensual</th>
                <th scope="col" className="px-3 py-2">Estado</th>
                <th scope="col" className="px-3 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {!isLoading && suppliers.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-slate-500" colSpan={6}>
                    No hay proveedores que coincidan con los filtros seleccionados.
                  </td>
                </tr>
              ) : null}

              {suppliers.map((supplier) => {
                const isArchived = supplier.archived_at !== null;
                const isSuspended = supplier.status === "suspended";
                const draft = rateDrafts[supplier.id] ?? String(supplier.monthly_rate);
                const isBusy = rowBusyId === supplier.id;

                return (
                  <tr
                    key={supplier.id}
                    className={`border-b border-slate-100 align-top ${isSuspended ? "bg-slate-50 text-slate-500" : "text-slate-800"}`}
                  >
                    <th scope="row" className="px-3 py-3 text-left font-medium">
                      <span className={isSuspended ? "line-through decoration-slate-400" : ""}>
                        {supplier.name}
                      </span>
                      <span className="mt-1 block text-xs font-normal text-slate-500">
                        {supplier.compliance_agreement
                          ? `Acuerdo: ${supplier.compliance_agreement}`
                          : "Sin acuerdo de cumplimiento"}
                      </span>
                    </th>
                    <td className="px-3 py-3">{supplier.country}</td>
                    <td className="px-3 py-3">
                      <ul className="flex flex-wrap gap-1">
                        {supplier.categories.map((category) => (
                          <li
                            key={category}
                            className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                          >
                            {CATEGORY_LABELS[category]}
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="px-3 py-3">
                      <span className="block font-semibold">{formatRate(supplier)}</span>
                      <span className="mt-1 block text-xs text-slate-500">
                        Actualizada: {formatTimestamp(supplier.updated_at)}
                      </span>
                      <div className="mt-2 flex items-center gap-2">
                        <label className="sr-only" htmlFor={`rate-${supplier.id}`}>
                          Nueva tarifa mensual para {supplier.name}
                        </label>
                        <input
                          id={`rate-${supplier.id}`}
                          type="number"
                          min="0.01"
                          step="0.01"
                          className="w-28 rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                          value={draft}
                          onChange={(event) =>
                            setRateDrafts((current) => ({
                              ...current,
                              [supplier.id]: event.target.value,
                            }))
                          }
                        />
                        <button
                          type="button"
                          className="rounded-lg bg-cyan-700 px-3 py-1 text-xs font-semibold text-white hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
                          disabled={isBusy}
                          onClick={() => void handleRateUpdate(supplier)}
                        >
                          Guardar
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                          isArchived
                            ? "bg-red-100 text-red-800"
                            : isSuspended
                              ? "bg-amber-100 text-amber-800"
                              : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {isArchived ? "Eliminado" : isSuspended ? "Suspendido" : "Activo"}
                      </span>
                      {isArchived && supplier.archived_at ? (
                        <span className="mt-1 block text-xs text-slate-500">
                          Baja: {formatTimestamp(supplier.archived_at)}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
                          disabled={isBusy}
                          onClick={() => void handleStatusToggle(supplier)}
                        >
                          {isSuspended ? "Activar" : "Suspender"}
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-red-300 px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                          disabled={isBusy || isArchived}
                          onClick={() => void handleArchive(supplier)}
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section
        aria-labelledby="create-heading"
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3 id="create-heading" className="text-lg font-semibold text-slate-900">
          Registrar proveedor
        </h3>

        <form className="mt-4 space-y-4" onSubmit={handleCreate} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-name">
                Nombre comercial
              </label>
              <input
                id="supplier-name"
                type="text"
                required
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? "supplier-name-error" : undefined}
                className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 ${fieldErrors.name ? "border-red-500" : "border-slate-300 focus:border-cyan-600"}`}
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
              {fieldErrors.name ? (
                <p id="supplier-name-error" className="mt-1 text-xs text-red-700">
                  {fieldErrors.name}
                </p>
              ) : null}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-country">
                País del contrato
              </label>
              <select
                id="supplier-country"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={form.country}
                onChange={(event) =>
                  setForm({ ...form, country: event.target.value as SupplierCountry })
                }
              >
                {SUPPLIER_COUNTRIES.map((country) => (
                  <option key={country} value={country}>
                    {country}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">
                Moneda asignada automáticamente: {CURRENCY_BY_COUNTRY[form.country]}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-rate">
                Tarifa mensual
              </label>
              <input
                id="supplier-rate"
                type="number"
                min="0.01"
                step="0.01"
                required
                aria-invalid={Boolean(fieldErrors.monthlyRate)}
                aria-describedby={fieldErrors.monthlyRate ? "supplier-rate-error" : undefined}
                className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 ${fieldErrors.monthlyRate ? "border-red-500" : "border-slate-300 focus:border-cyan-600"}`}
                value={form.monthlyRate}
                onChange={(event) => setForm({ ...form, monthlyRate: event.target.value })}
              />
              {fieldErrors.monthlyRate ? (
                <p id="supplier-rate-error" className="mt-1 text-xs text-red-700">
                  {fieldErrors.monthlyRate}
                </p>
              ) : null}
            </div>

            <div>
              <label
                className="block text-sm font-medium text-slate-700"
                htmlFor="supplier-compliance"
              >
                Acuerdo de cumplimiento
              </label>
              <select
                id="supplier-compliance"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={form.complianceAgreement}
                onChange={(event) =>
                  setForm({
                    ...form,
                    complianceAgreement: event.target.value as ComplianceAgreement | "",
                  })
                }
              >
                <option value="">No aplica</option>
                {COMPLIANCE_AGREEMENTS.map((agreement) => (
                  <option key={agreement} value={agreement}>
                    {agreement}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-renewal">
                Fecha de renovación
              </label>
              <input
                id="supplier-renewal"
                type="date"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={form.contractRenewalDate}
                onChange={(event) => setForm({ ...form, contractRenewalDate: event.target.value })}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-email">
                Email del account manager
              </label>
              <input
                id="supplier-email"
                type="email"
                aria-invalid={Boolean(fieldErrors.contactEmail)}
                aria-describedby={fieldErrors.contactEmail ? "supplier-email-error" : undefined}
                className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 ${fieldErrors.contactEmail ? "border-red-500" : "border-slate-300 focus:border-cyan-600"}`}
                value={form.contactEmail}
                onChange={(event) => setForm({ ...form, contactEmail: event.target.value })}
              />
              {fieldErrors.contactEmail ? (
                <p id="supplier-email-error" className="mt-1 text-xs text-red-700">
                  {fieldErrors.contactEmail}
                </p>
              ) : null}
            </div>
          </div>

          <fieldset className="rounded-lg border border-slate-200 p-3">
            <legend className="px-1 text-sm font-medium text-slate-700">
              Categorías (mínimo una)
            </legend>
            {fieldErrors.categories ? (
              <p className="mt-1 text-xs text-red-700">{fieldErrors.categories}</p>
            ) : null}
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {SUPPLIER_CATEGORIES.map((category) => (
                <label key={category} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-cyan-700 focus:ring-2 focus:ring-cyan-500"
                    checked={form.categories.includes(category)}
                    onChange={() => toggleFormCategory(category)}
                  />
                  {CATEGORY_LABELS[category]}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="block text-sm font-medium text-slate-700" htmlFor="supplier-notes">
              Observaciones internas
            </label>
            <textarea
              id="supplier-notes"
              rows={3}
              maxLength={500}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              value={form.notes}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
            />
          </div>

          <div aria-live="assertive">
            {formError ? (
              <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </p>
            ) : null}
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
            >
              {isSubmitting ? "Registrando…" : "Registrar proveedor"}
            </button>
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              onClick={() => {
                setForm(EMPTY_FORM);
                setFormError(null);
                setFieldErrors({});
              }}
            >
              Limpiar formulario
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
