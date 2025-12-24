import { notFound } from "next/navigation";
import { Metadata } from "next";
import { fetchLocales } from "@/lib/api";
import LocalePage from "./LocalePage";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale: localeSlug } = await params;
  const locales = await fetchLocales();
  const locale = locales.find((l) => l.slug === localeSlug.toLowerCase());

  if (!locale) {
    return {
      title: "Not Found - earthquake.city",
    };
  }

  return {
    title: `${locale.display_name} Earthquakes - earthquake.city`,
    description: `Track real-time earthquakes in ${locale.display_name}. See time since last M${locale.min_magnitude}+ earthquake.`,
    openGraph: {
      title: `${locale.display_name} Earthquake Tracker`,
      description: `Real-time earthquake monitoring for ${locale.display_name}`,
    },
  };
}

export async function generateStaticParams() {
  const locales = await fetchLocales();
  return locales.map((locale) => ({
    locale: locale.slug,
  }));
}

export default async function Page({ params }: PageProps) {
  const { locale: localeSlug } = await params;
  const allLocales = await fetchLocales();
  const locale = allLocales.find((l) => l.slug === localeSlug.toLowerCase());

  if (!locale) {
    notFound();
  }

  return (
    <LocalePage
      localeSlug={locale.slug}
      initialDisplayName={locale.display_name}
      initialCenter={locale.center}
      initialMinMagnitude={locale.min_magnitude}
      allLocales={allLocales}
    />
  );
}
