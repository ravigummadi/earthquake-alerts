import Link from "next/link";
import { fetchLocales } from "@/lib/api";

export default async function NotFound() {
  const locales = await fetchLocales();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="text-center space-y-6 max-w-md">
        <div className="w-20 h-20 mx-auto rounded-full bg-slate-800 flex items-center justify-center">
          <svg
            className="w-10 h-10 text-slate-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-white">Location Not Found</h1>

        <p className="text-slate-400">
          We don't have earthquake data for this location yet. Choose from our
          available regions:
        </p>

        <div className="flex flex-wrap justify-center gap-3">
          {locales.map((locale) => (
            <Link
              key={locale.slug}
              href={`/${locale.slug}`}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg
                         font-medium transition-colors"
            >
              {locale.display_name}
            </Link>
          ))}
        </div>

        <Link
          href="/"
          className="inline-block text-primary-400 hover:text-primary-300 text-sm"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
