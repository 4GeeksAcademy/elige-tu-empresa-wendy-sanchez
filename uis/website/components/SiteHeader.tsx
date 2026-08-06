import Link from "next/link";
import Image from "next/image";
import { WebsiteContent } from "@/types/website";

interface SiteHeaderProps {
  content: WebsiteContent;
}

export default function SiteHeader({ content }: SiteHeaderProps) {
  const isSpanish = content.lang === "es";

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <a href={`#${content.homeAnchor}`} className="flex items-center gap-3" aria-label={content.homeAriaLabel}>
          <Image
            src="https://images.unsplash.com/photo-1631815588090-d4bfec5b1ccb?auto=format&fit=crop&w=120&q=80"
            alt={isSpanish ? "Simbolo medico de cruz de HealthCore" : "HealthCore medical cross symbol"}
            className="h-10 w-10 rounded-xl object-cover"
            width={40}
            height={40}
          />
          <span className="text-lg font-semibold tracking-tight text-slate-800">HealthCore</span>
        </a>

        <nav aria-label={content.navLabel} className="hidden md:block">
          <ul className="flex items-center gap-6 text-sm font-medium text-slate-700">
            {content.navItems.map((item) => (
              <li key={item.href}>
                <a
                  className="hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
                  href={item.href}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex items-center gap-2" aria-label={isSpanish ? "Selector de idioma" : "Language selector"}>
          <Link
            href="/"
            lang="en"
            aria-current={!isSpanish ? "page" : undefined}
            className={!isSpanish ? "rounded-full bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white" : "rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"}
          >
            EN
          </Link>
          <Link
            href="/es"
            lang="es"
            aria-current={isSpanish ? "page" : undefined}
            className={isSpanish ? "rounded-full bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white" : "rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"}
          >
            ES
          </Link>
        </div>
      </div>

      <nav aria-label={content.mobileNavLabel} className="border-t border-slate-200 bg-white md:hidden">
        <ul className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 text-xs font-semibold text-slate-700 sm:px-6">
          {content.navItems.map((item) => (
            <li key={`mobile-${item.href}`}>
              <a
                className="rounded px-2 py-1 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
                href={item.href}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
