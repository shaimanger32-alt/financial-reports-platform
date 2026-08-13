import { CompanyReport } from "@/components/CompanyReport";
import { toLocale } from "@/lib/i18n";

/** A company, on its most recent quarter. */
export default async function CompanyPage({ params }: PageProps<"/[locale]/companies/[id]">) {
  const { id, locale } = await params;
  return <CompanyReport id={id} locale={toLocale(locale)} />;
}
