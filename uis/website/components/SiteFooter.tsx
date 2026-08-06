import { WebsiteContent } from "@/types/website";

interface SiteFooterProps {
  content: WebsiteContent;
}

export default function SiteFooter({ content }: SiteFooterProps) {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <p>{content.footerCopyright}</p>
        <nav aria-label={content.socialNavLabel}>
          <ul className="flex items-center gap-4">
            <li>
              <a className="hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2" href="https://linkedin.com/company/healthcore">
                LinkedIn
              </a>
            </li>
            <li>
              <a className="hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2" href="https://facebook.com/healthcore">
                Facebook
              </a>
            </li>
            <li>
              <a className="hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2" href="https://instagram.com/healthcore">
                Instagram
              </a>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}
