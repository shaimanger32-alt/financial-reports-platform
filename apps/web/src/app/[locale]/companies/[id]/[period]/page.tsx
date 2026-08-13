import { CompanyReport } from "@/components/CompanyReport";
import { toLocale } from "@/lib/i18n";

/**
 * A company, on one named period.
 *
 * Its own address rather than a query parameter, so a reader who finds
 * something in a particular quarter can send someone the quarter.
 */
export default async function CompanyPeriodPage({
  params,
}: PageProps<"/[locale]/companies/[id]/[period]">) {
  const { id, locale, period } = await params;
  return <CompanyReport id={id} locale={toLocale(locale)} period={period} />;
}
