"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

interface LocaleNav {
  slug: string;
  name: string;
}

interface HeaderProps {
  currentLocale: string;
  locales?: LocaleNav[];
}

// Fallback for initial render before API data loads
const DEFAULT_LOCALES: LocaleNav[] = [
  { slug: "sanramon", name: "San Ramon" },
  { slug: "bayarea", name: "Bay Area" },
  { slug: "la", name: "Los Angeles" },
];

export default function Header({ currentLocale, locales = DEFAULT_LOCALES }: HeaderProps) {
  const router = useRouter();

  const handleLocaleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    router.push(`/${e.target.value}`);
  };

  return (
    <header className="w-full py-4 px-4 md:px-6">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 text-white hover:text-primary-400 transition-colors"
          aria-label="earthquake.city home"
        >
          <svg
            className="w-6 h-6 md:w-8 md:h-8"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" strokeWidth="1.5" />
            <path
              d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"
              strokeWidth="1.5"
            />
          </svg>
          <span className="text-lg md:text-xl font-semibold">
            earthquake<span className="text-primary-400">.city</span>
          </span>
        </Link>

        <div className="relative">
          <select
            value={currentLocale}
            onChange={handleLocaleChange}
            aria-label="Select location"
            className="appearance-none bg-slate-800/50 border border-slate-700 text-white text-sm
                       rounded-lg pl-3 pr-8 py-2 cursor-pointer
                       hover:bg-slate-700/50 hover:border-slate-600
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                       transition-colors"
          >
            {locales.map((locale) => (
              <option key={locale.slug} value={locale.slug}>
                {locale.name}
              </option>
            ))}
          </select>
          <svg
            className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </header>
  );
}
