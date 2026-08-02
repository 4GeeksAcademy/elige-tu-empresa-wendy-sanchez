import { WebsiteContent } from "@/types/website";
import Image from "next/image";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

interface LandingPageProps {
  content: WebsiteContent;
}

export default function LandingPage({ content }: LandingPageProps) {
  const servicesId = content.lang === "es" ? "servicios" : "services";
  const locationsId = content.lang === "es" ? "ubicaciones" : "locations";
  const contactId = content.lang === "es" ? "contacto" : "contact";
  const heroId = content.lang === "es" ? "hero-title-es" : "hero-title";

  return (
    <>
      <SiteHeader content={content} />

      <main id={content.homeAnchor} className="min-h-screen">
        <section
          className="relative overflow-hidden border-b border-slate-200 bg-gradient-to-br from-sky-900 via-cyan-800 to-teal-700"
          aria-labelledby={heroId}
        >
          <div className="absolute inset-0 opacity-20" aria-hidden="true">
            <div className="h-full w-full bg-[radial-gradient(circle_at_15%_20%,white_0%,transparent_40%),radial-gradient(circle_at_85%_80%,#a5f3fc_0%,transparent_35%)]" />
          </div>

          <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 sm:py-20 md:grid-cols-2 md:items-center lg:px-8 lg:py-24">
            <article>
              <p className="inline-flex rounded-full bg-white/15 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-cyan-100">
                {content.heroBadge}
              </p>
              <h1 id={heroId} className="mt-5 text-3xl font-bold leading-tight text-white sm:text-4xl lg:text-5xl">
                {content.heroTitle}
              </h1>
              <p className="mt-5 max-w-xl text-base text-cyan-50 sm:text-lg">{content.heroSubtitle}</p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <a
                  href="/application"
                  className="inline-flex items-center justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold text-sky-900 shadow-sm transition hover:bg-cyan-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-sky-800"
                >
                  {content.heroPrimaryCta}
                </a>
                <a
                  href={`#${servicesId}`}
                  className="inline-flex items-center justify-center rounded-xl border border-cyan-200/80 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-sky-800"
                >
                  {content.heroSecondaryCta}
                </a>
              </div>
            </article>

            <figure className="rounded-2xl border border-white/20 bg-white/10 p-3 backdrop-blur-sm">
              <Image
                src="https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=1400&q=80"
                alt={content.heroImageAlt}
                className="h-72 w-full rounded-xl object-cover sm:h-80 lg:h-[26rem]"
                width={1400}
                height={832}
              />
            </figure>
          </div>
        </section>

        <section id={servicesId} className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
          <header className="max-w-2xl">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{content.servicesTitle}</h2>
            <p className="mt-3 text-sm text-slate-600 sm:text-base">{content.servicesSubtitle}</p>
          </header>

          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {content.services.map((service) => (
              <article key={service.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">{service.title}</h3>
                <ul className="mt-4 space-y-2 text-sm text-slate-700">
                  {service.bullets.map((item) => (
                    <li key={`${service.title}-${item}`}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="border-y border-slate-200 bg-white">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-2 lg:px-8 lg:py-20">
            <article>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{content.whyTitle}</h2>
              <ul className="mt-5 space-y-4 text-sm text-slate-700 sm:text-base">
                {content.whyItems.map((item) => (
                  <li key={`${item.emphasis}-${item.text}`}>
                    <strong>{item.emphasis}</strong> {item.text}
                  </li>
                ))}
              </ul>
            </article>

            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
              <h3 className="text-lg font-semibold text-slate-900">{content.whyCardTitle}</h3>
              <p className="mt-3 text-sm text-slate-700">{content.whyCardBody}</p>
              <a
                href="/application"
                className="mt-6 inline-flex items-center rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-700 focus:ring-offset-2"
              >
                {content.whyCardCta}
              </a>
            </article>
          </div>
        </section>

        <section id={locationsId} className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
          <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{content.locationsTitle}</h2>
            <p className="text-xs text-slate-500 sm:text-sm">{content.locationsNote}</p>
          </header>

          <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm" aria-label={content.locationsTableLabel}>
                <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th scope="col" className="px-4 py-3">{content.locationsColumns.clinic}</th>
                    <th scope="col" className="px-4 py-3">{content.locationsColumns.city}</th>
                    <th scope="col" className="px-4 py-3">{content.locationsColumns.state}</th>
                    <th scope="col" className="px-4 py-3">{content.locationsColumns.phone}</th>
                    <th scope="col" className="px-4 py-3">{content.locationsColumns.hours}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {content.locations.map((location) => (
                    <tr key={location.name}>
                      <td className="px-4 py-3 font-medium">{location.name}</td>
                      <td className="px-4 py-3">{location.city}</td>
                      <td className="px-4 py-3">{location.state}</td>
                      <td className="px-4 py-3">{location.phone}</td>
                      <td className="px-4 py-3">{location.hours}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section id={contactId} className="border-t border-slate-200 bg-slate-100">
          <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{content.contactTitle}</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {content.contactCards.map((card) => (
                <article key={card.title} className="rounded-xl bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-slate-800">{card.title}</h3>
                  <p className="mt-2 text-sm text-slate-700">{card.value}</p>
                </article>
              ))}
            </div>

            <p className="mt-8 text-sm text-slate-600">{content.contactBody}</p>
            <a
              href="/application"
              className="mt-4 inline-flex items-center rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-700 focus:ring-offset-2"
            >
              {content.contactPrimaryCta}
            </a>
          </div>
        </section>
      </main>

      <SiteFooter content={content} />
    </>
  );
}
