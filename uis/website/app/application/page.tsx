import Link from "next/link";

export default function ApplicationPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-4 py-16 sm:px-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-sky-700">HealthCore</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900">Patient inquiry form</h1>
        <p className="mt-3 text-slate-700">
          This route is reserved for the Next.js migration. The full interactive intake form still lives in the legacy milestone file for now.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/"
            className="rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800"
          >
            Back to website
          </Link>
          <a
            href="/application.html"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Open legacy form
          </a>
        </div>
      </div>
    </main>
  );
}
