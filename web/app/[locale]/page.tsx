import { notFound } from "next/navigation";
import { Metadata } from "next";
import { getLocale, LOCALES } from "@/config/locales";
import LocalePage from "./LocalePage";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale: localeSlug } = await params;
  const locale = getLocale(localeSlug);

  if (!locale) {
    return {
      title: "Not Found - earthquake.city",
    };
  }

  return {
    title: `${locale.displayName} Earthquakes - earthquake.city`,
    description: `Track real-time earthquakes in ${locale.displayName}. See time since last M${locale.minMagnitude}+ earthquake with an interactive 3D globe.`,
    openGraph: {
      title: `${locale.displayName} Earthquake Tracker`,
      description: `Real-time earthquake monitoring for ${locale.displayName}`,
    },
  };
}

export function generateStaticParams() {
  return Object.keys(LOCALES).map((locale) => ({
    locale,
  }));
}

export default async function Page({ params }: PageProps) {
  const { locale: localeSlug } = await params;
  const locale = getLocale(localeSlug);

  if (!locale) {
    notFound();
  }

  return <LocalePage locale={locale} />;
}
