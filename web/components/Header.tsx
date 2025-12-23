"use client";

import Link from "next/link";
import { getAllLocales } from "@/config/locales";

interface HeaderProps {
  currentLocale: string;
}

export default function Header({ currentLocale }: HeaderProps) {
  const locales = getAllLocales();

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

        <nav className="flex items-center gap-1 md:gap-2" aria-label="Locale selection">
          {locales.map((locale) => (
            <Link
              key={locale.slug}
              href={`/${locale.slug}`}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                currentLocale === locale.slug
                  ? "bg-primary-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
              aria-current={currentLocale === locale.slug ? "page" : undefined}
            >
              {locale.name}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
