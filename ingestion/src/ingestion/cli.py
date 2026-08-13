"""Exploration CLI for the MAGNA provider.

Read-only. Nothing here writes to the database; that begins in phase 2.

    python -m ingestion.cli entities
    python -m ingestion.cli concepts --contains receivable
    python -m ingestion.cli coverage --from-year 2022 --to-year 2025
    python -m ingestion.cli facts --entity 520039413 --from-year 2023 --to-year 2024
"""

import argparse
import collections
import logging
import sys
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from database import session_scope
from database.models import AnalysisSnapshot as AnalysisSnapshotRow
from database.models import Company
from database.repository import find_company, load_fact_set, load_metric_series
from financial_core.metrics import CALCULATED_BY_CODE, compute_all
from financial_core.periods import cumulative_period, discrete_period
from financial_core.signals import ALL_RULES, CORE_RULES, DEFAULT_THRESHOLDS, evaluate_all
from ingestion.archive import RawArchive
from ingestion.config import get_ingestion_settings
from ingestion.core_concepts import CORE_CONCEPTS
from ingestion.pipelines.magna import ingest_batch
from ingestion.pipelines.snapshots import generate_snapshots
from ingestion.providers.base import FactQuery, ProviderFact
from ingestion.providers.magna_xbrl import (
    MagnaXbrlClient,
    all_mapped_concepts,
    distinct_filings,
    find_conflicts,
)
from ingestion.seeding import seed_reference_data

logger = logging.getLogger("ingestion.cli")


def _archive(payload: bytes, kind: str, source_reference: str) -> None:
    archive = RawArchive(get_ingestion_settings().raw_archive_dir)
    stored = archive.store(
        payload,
        provider="magna_xbrl",
        kind=kind,
        source_reference=source_reference,
    )
    state = "already archived" if stored.already_present else "archived"
    print(f"\n{state}: {stored.path}")


def cmd_entities(args: argparse.Namespace) -> int:
    with MagnaXbrlClient() as client:
        entities = client.list_entities()
        payload = client.raw_init_bytes

    by_sector: dict[str, list[str]] = collections.defaultdict(list)
    for entity in entities:
        label = f"{entity.provider_entity_id}  {entity.name_en or entity.name}"
        by_sector[entity.sector_name or "unknown"].append(label)

    print(f"{len(entities)} entities in {len(by_sector)} sectors\n")
    for sector, members in sorted(by_sector.items(), key=lambda kv: -len(kv[1])):
        print(f"{sector}  ({len(members)})")
        for member in sorted(members):
            print(f"    {member}")
        print()

    if args.archive:
        _archive(payload, "init", "magna_xbrl:init")
    return 0


def cmd_concepts(args: argparse.Namespace) -> int:
    with MagnaXbrlClient() as client:
        concepts = client.list_concepts()

    needle = (args.contains or "").lower()
    matched = [c for c in concepts if needle in c.name.lower()]
    extensions = sum(1 for c in matched if c.is_extension)

    print(
        f"{len(matched)} of {len(concepts)} concepts match; {extensions} are company extensions\n"
    )
    for concept in sorted(matched, key=lambda c: c.name):
        marker = "ext" if concept.is_extension else "   "
        print(f"  {marker}  {concept.name:<72}  {concept.label or ''}")
    return 0


def _print_coverage(facts: Sequence[ProviderFact], entity_names: dict[str, str]) -> None:
    usable = [f for f in facts if not f.is_dimensional and f.value is not None]
    periods: dict[str, dict[str, set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    filings: dict[str, set[str]] = collections.defaultdict(set)
    for fact in usable:
        periods[fact.provider_entity_id][fact.concept].add(fact.period.raw)
        filings[fact.provider_entity_id].add(fact.provider_filing_id)

    concepts = list(CORE_CONCEPTS)
    header = "".join(f"{CORE_CONCEPTS[c][:6]:>8}" for c in concepts)
    print(f"\n{'Entity':<40}{'Filings':>8}{header}")
    print("-" * (48 + 8 * len(concepts)))

    def score(entity_id: str) -> tuple[int, int]:
        return (sum(1 for c in concepts if periods[entity_id][c]), len(filings[entity_id]))

    for entity_id in sorted(periods, key=score, reverse=True):
        name = entity_names.get(entity_id, entity_id)[:38]
        cells = "".join(
            f"{len(periods[entity_id][c]):>8}" if periods[entity_id][c] else f"{'-':>8}"
            for c in concepts
        )
        print(f"{name:<40}{len(filings[entity_id]):>8}{cells}")


def cmd_coverage(args: argparse.Namespace) -> int:
    with MagnaXbrlClient() as client:
        entities = client.list_entities()
        names = {e.provider_entity_id: (e.name_en or e.name) for e in entities}
        batch = client.fetch_facts(
            FactQuery(
                entity_ids=(),
                concepts=tuple(CORE_CONCEPTS),
                from_year=args.from_year,
                to_year=args.to_year,
            )
        )

    print(f"{len(batch.facts)} facts parsed from {len(batch.raw_payload):,} bytes")
    _print_coverage(batch.facts, names)

    if args.archive:
        _archive(batch.raw_payload, "search", batch.source_reference)
    return 0


def cmd_facts(args: argparse.Namespace) -> int:
    with MagnaXbrlClient() as client:
        batch = client.fetch_facts(
            FactQuery(
                entity_ids=(args.entity,),
                concepts=tuple(CORE_CONCEPTS),
                from_year=args.from_year,
                to_year=args.to_year,
            )
        )

    facts = batch.facts
    usable = [f for f in facts if not f.is_dimensional]
    print(f"facts: {len(facts)}   undimensioned: {len(usable)}")
    print(f"without a value: {sum(1 for f in usable if f.value is None)}")

    discovered = distinct_filings(facts)
    print(f"\nfilings discovered: {len(discovered)}")
    for filing_id in sorted(discovered):
        print(f"    {filing_id}")

    instants = sum(1 for f in usable if f.period.kind == "instant")
    print(f"\nperiods: {instants} instant, {len(usable) - instants} duration")

    conflicts = find_conflicts(usable)
    print(f"\nfacts restated across filings: {len(conflicts)}")
    for (entity, concept, period, _), values in sorted(conflicts.items()):
        readable = ", ".join(
            f"{v:,.0f}" if v is not None else "null"
            for v in sorted(values, key=lambda x: (x is None, x))
        )
        print(f"    {entity}  {concept}  {period}  ->  {readable}")

    if args.archive:
        _archive(batch.raw_payload, "search", batch.source_reference)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    with MagnaXbrlClient() as client:
        entities = {e.provider_entity_id: e for e in client.list_entities()}
        entity = entities.get(args.entity)
        if entity is None:
            print(f"unknown entity {args.entity}; try `entities` to list them")
            return 1

        batch = client.fetch_facts(
            FactQuery(
                entity_ids=(args.entity,),
                concepts=all_mapped_concepts(),
                from_year=args.from_year,
                to_year=args.to_year,
            )
        )

    if args.archive:
        _archive(batch.raw_payload, "search", batch.source_reference)

    with session_scope() as session:
        seed = seed_reference_data(session)
        report = ingest_batch(session, entity, batch)
        # Spec section 32 step 9: the snapshot is part of ingestion, not a
        # separate chore. A company that is loaded but has no snapshot is
        # invisible to the API, which is a confusing half-state to leave behind.
        company = find_company(session, args.entity)
        snapshots = generate_snapshots(session, company) if company else None

    print(f"\n{entity.name_en or entity.name}")
    print(f"  reference data   {seed.metrics} metrics, {seed.mappings} mappings")
    print(f"  filings          {report.filings}")
    print(f"  periods          {report.periods}")
    print(f"  reported facts   {report.reported_facts}")
    print(f"  derived facts    {report.derived_facts}")
    if snapshots:
        print(
            f"  snapshots        {snapshots.generated}, "
            f"{snapshots.signals} signals, {snapshots.patterns} patterns"
        )
    print(f"  without a value  {report.facts_without_value}")
    if report.mixed_vintage_derivations:
        print(
            f"  cross-filing     {report.mixed_vintage_derivations} derivations "
            f"(inputs from different filings, flagged usable_with_warning)"
        )

    if report.skipped_unclassifiable_periods:
        print(
            f"  skipped periods  {report.skipped_unclassifiable_periods} (not a calendar quarter)"
        )
    if report.unmapped_concepts:
        print(f"  unmapped         {len(report.unmapped_concepts)} concepts stored raw")

    if report.restatements:
        print(f"\nrestatements ({len(report.restatements)}):")
        for restatement in report.restatements:
            print(
                f"    {restatement.concept} @ {restatement.period_code}: "
                f"{restatement.earlier_value:,.0f} ({restatement.earlier_filing}) -> "
                f"{restatement.later_value:,.0f} ({restatement.later_filing})"
            )

    if report.derivation_mismatches:
        print(
            f"\nderived quarters disagreeing with the issuer ({len(report.derivation_mismatches)}):"
        )
        for mismatch in report.derivation_mismatches:
            print(
                f"    {mismatch.concept} @ {mismatch.period_code}: "
                f"reported {mismatch.reported:,.0f}, derived {mismatch.derived:,.0f}"
            )

    if report.unrecognised_references:
        print(
            f"\nfiling references of an unexpected shape: {sorted(report.unrecognised_references)}"
        )

    return 0


def cmd_ingest_us(args: argparse.Namespace) -> int:
    """Load one American company from SEC EDGAR.

    The fiscal calendar is learned before anything is classified. A company that
    has filed no annual report yet declares no fiscal years, and nothing can be
    placed on a calendar that does not exist -- so it is refused rather than
    forced onto December.
    """
    import json as _json

    from ingestion.pipelines.sec_edgar import ingest_batch as ingest_us_batch
    from ingestion.providers.sec_edgar import SecEdgarClient, learn_fiscal_calendar, normalise_cik

    client = SecEdgarClient()
    entities = {e.provider_entity_id: e for e in client.list_entities()}

    requested = [normalise_cik(value) for value in args.cik]
    unknown = [cik for cik in requested if cik not in entities]
    if unknown:
        print(f"not in SEC's ticker index: {', '.join(unknown)}")
        return 1

    failures = 0
    for cik in requested:
        entity = entities[cik]
        batch = client.fetch_facts(
            FactQuery(entity_ids=(cik,), from_year=args.from_year, to_year=args.to_year)
        )
        calendar = learn_fiscal_calendar(_json.loads(batch.raw_payload))

        if args.archive:
            _archive(batch.raw_payload, "companyfacts", batch.source_reference)

        if calendar.is_empty:
            print(f"{entity.name}: no annual report, so no fiscal calendar. Nothing loaded.")
            failures += 1
            continue

        with session_scope() as session:
            seed_reference_data(session)
            report = ingest_us_batch(session, entity, batch, calendar)
            company = find_company(session, cik, provider="sec_edgar")
            if company is not None and args.publish:
                company.is_published = True
            snapshots = generate_snapshots(session, company) if company else None

        published = "published" if args.publish else "not published"
        print(
            f"{entity.name[:34]:36} CIK {cik}  "
            f"FY {report.fiscal_years:>2}  facts {report.facts:>6,}  "
            f"snapshots {snapshots.generated if snapshots else 0:>3}  "
            f"signals {snapshots.signals if snapshots else 0:>3}  "
            f"patterns {snapshots.patterns if snapshots else 0:>2}  {published}"
        )

    return 1 if failures else 0


def cmd_snapshots(args: argparse.Namespace) -> int:
    """Rebuild snapshots for every company, without touching a provider.

    Ingestion writes a snapshot as it goes, but a change to a formula, a rule or
    a tiering leaves every stored snapshot describing the old engine. Re-running
    ingestion to pick that up would re-download the whole market for no reason,
    and would silently depend on the provider still being reachable.
    """
    with session_scope() as session:
        seed_reference_data(session)
        companies = list(session.scalars(select(Company).order_by(Company.display_name)))
        if args.entity:
            companies = [c for c in companies if c.provider_entity_id in set(args.entity)]

        total = signals = patterns = 0
        for company in companies:
            report = generate_snapshots(session, company)
            total += report.generated
            signals += report.signals
            patterns += report.patterns
            print(
                f"  {(company.name_en or company.legal_name)[:34]:36} "
                f"{report.generated:>4} snapshots  {report.signals:>3} signals  "
                f"{report.patterns:>2} patterns"
            )

    print(
        f"\n{len(companies)} companies, {total} snapshots, {signals} signals, {patterns} patterns"
    )
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    """Where the accounting identities do not close.

    A development tool, deliberately not a page. A broken identity is far more
    often our mapping than the issuer's arithmetic, so the audience for it is
    whoever can fix the mapping -- not a reader, who would be told that a
    perfectly sound filing does not add up.

    `unreported terms` is the first thing to look at. A cash bridge off by a
    fraction at a company that filed no exchange-rate line is a gap in our
    concept chain; one at a company that filed the line is worth opening the
    filing for.
    """
    from financial_core.validation import IdentityOutcome

    with session_scope() as session:
        companies = list(session.scalars(select(Company).order_by(Company.display_name)))
        rows: list[tuple[str, str, dict[str, Any]]] = []
        totals: collections.Counter[str] = collections.Counter()

        for company in companies:
            snapshots = [
                row.payload_json
                for row in session.scalars(
                    select(AnalysisSnapshotRow).where(
                        AnalysisSnapshotRow.company_id == company.id,
                        AnalysisSnapshotRow.is_current,
                    )
                )
            ]
            if not snapshots:
                continue
            typed: list[dict[str, Any]] = [dict(payload) for payload in snapshots]
            chosen = (
                typed if args.all_periods else [max(typed, key=lambda p: str(p["period_code"]))]
            )

            name = company.name_en or company.legal_name
            for payload in chosen:
                identities = payload.get("identities") or []
                if not identities:
                    totals["no_checks_stored"] += 1
                for identity in identities:
                    outcome = str(identity["outcome"])
                    totals[outcome] += 1
                    if outcome == IdentityOutcome.BROKEN.value or args.verbose_checks:
                        rows.append((name, str(payload["period_code"]), identity))

    basics = _basic_findings(args)

    scope = "every period" if args.all_periods else "the latest period of each company"
    print(f"Accounting identities across {len(companies)} companies, {scope}\n")
    for outcome, count in sorted(totals.items()):
        print(f"  {outcome:18} {count}")

    if not rows:
        print("\nNothing broken.")
        return 0

    print(f"\n{'company':32} {'period':10} {'identity':40} {'gap':>9}  note")
    print("-" * 110)
    for name, period, identity in rows:
        relative = identity.get("relative_difference")
        gap = f"{float(relative) * 100:.2f}%" if isinstance(relative, int | float) else "-"
        unreported = identity.get("unreported_terms") or []
        missing = identity.get("missing") or []
        if unreported:
            note = f"no {', '.join(str(t) for t in unreported)} filed -- likely our mapping"
        elif missing:
            note = f"not checkable: {', '.join(str(m) for m in missing)}"
        else:
            note = "every term present -- worth opening the filing"
        print(f"  {name[:30]:32} {period:10} {str(identity['name'])[:38]:40} {gap:>9}  {note}")

    if basics:
        print(f"\nBasic validation (section 21.1): {len(basics)} findings")
        print(f"\n  {'company':30} {'issue':26} {'metric':28} detail")
        print("  " + "-" * 108)
        for name, finding in basics:
            print(
                f"  {name[:28]:30} {finding.issue.value:26} "
                f"{finding.metric_code[:26]:28} {finding.detail}"
            )
    else:
        print("\nBasic validation (section 21.1): nothing.")

    broken = totals.get(IdentityOutcome.BROKEN.value, 0)
    return 1 if (broken or basics) and args.strict else 0


def _basic_findings(args: argparse.Namespace) -> list[tuple[str, Any]]:
    """Units, contradictory duplicates and values that cannot exist."""
    from database.repository import reported_observations
    from financial_core.validation import check_basics

    found: list[tuple[str, Any]] = []
    with session_scope() as session:
        for company in session.scalars(select(Company).order_by(Company.display_name)):
            if args.entity and company.provider_entity_id not in set(args.entity):
                continue
            name = company.name_en or company.legal_name
            for finding in check_basics(reported_observations(session, company.id)):
                found.append((name, finding))
    return found


def cmd_metrics(args: argparse.Namespace) -> int:
    """Print every computed metric for one period, so it can be checked by hand."""
    with session_scope() as session:
        company = find_company(session, args.entity)
        if company is None:
            print(f"{args.entity} has not been ingested; run `ingest` first")
            return 1

        facts = load_fact_set(session, company.id)
        period = (
            cumulative_period(args.year, args.quarter)
            if args.cumulative
            else discrete_period(args.year, args.quarter)
        )
        results = compute_all(facts, period)
        name = company.name_en or company.display_name

    print(f"\n{name} — {period.code}   ({len(facts)} facts available)\n")
    print(f"{'metric':<32}{'value':>18}  notes")
    print("-" * 78)
    for code in sorted(results):
        result = results[code]
        spec = CALCULATED_BY_CODE[code]
        if result.value is None:
            rendered = "—"
        elif spec.unit_type == "ratio":
            rendered = f"{result.value:,.4f}"
        elif spec.unit_type == "days":
            rendered = f"{result.value:,.1f} days"
        else:
            rendered = f"{result.value:,.0f}"

        notes = ", ".join(w.value for w in result.warnings)
        if result.value is None and result.missing_inputs:
            notes = f"missing: {', '.join(result.missing_inputs)}"
        print(f"{code:<32}{rendered:>18}  {notes}")

    print(f"\nformula version: {next(iter(results.values())).formula_version}")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """Show what the engine notices about a company, and what it stays quiet on."""
    with session_scope() as session:
        company = find_company(session, args.entity)
        if company is None:
            print(f"{args.entity} has not been ingested; run `ingest` first")
            return 1

        rules = CORE_RULES if args.core_only else ALL_RULES
        watched = sorted({rule.metric_code for rule in rules})
        series = load_metric_series(session, company.id, watched, quarters=args.quarters)
        signals = evaluate_all(rules, series, DEFAULT_THRESHOLDS, company.sector_name)
        name = company.name_en or company.display_name

    print(f"\n{name}   thresholds {DEFAULT_THRESHOLDS.version}, {len(watched)} metrics watched\n")

    if not signals:
        print("  nothing unusual against this company's own history")
    for signal in signals:
        change = signal.inputs.get("year_on_year_change")
        usual = signal.inputs.get("usual_change")
        print(f"  [{signal.severity.value:<8}] {signal.code}  ({signal.period.code})")
        print(
            f"             year on year {change:+,.2f}, usually {usual:+,.2f}, "
            f"{signal.deviation:+.1f} robust units"
        )
        print(
            f"             confidence {signal.confidence.value}, "
            f"persisted {signal.periods_persisted} period(s)"
        )

    quiet = [
        code
        for code in watched
        if series.get(code) and all(o.value is None for o in series[code].observations)
    ]
    if quiet:
        print(f"\n  no data at all for: {', '.join(quiet)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion.cli", description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="log HTTP and parsing detail")
    sub = parser.add_subparsers(dest="command", required=True)

    entities = sub.add_parser("entities", help="list reporting entities by sector")
    entities.add_argument("--archive", action="store_true", help="archive the raw init payload")
    entities.set_defaults(func=cmd_entities)

    concepts = sub.add_parser("concepts", help="list taxonomy concepts")
    concepts.add_argument("--contains", default="", help="case-insensitive substring filter")
    concepts.set_defaults(func=cmd_concepts)

    coverage = sub.add_parser("coverage", help="core concept coverage for every entity")
    coverage.add_argument("--from-year", type=int, required=True)
    coverage.add_argument("--to-year", type=int, required=True)
    coverage.add_argument("--archive", action="store_true")
    coverage.set_defaults(func=cmd_coverage)

    facts = sub.add_parser("facts", help="inspect one entity, including restatements")
    facts.add_argument("--entity", required=True, help="registrar number, e.g. 520039413")
    facts.add_argument("--from-year", type=int, required=True)
    facts.add_argument("--to-year", type=int, required=True)
    facts.add_argument("--archive", action="store_true")
    facts.set_defaults(func=cmd_facts)

    ingest = sub.add_parser("ingest", help="load one company into the canonical store")
    ingest.add_argument("--entity", required=True, help="registrar number, e.g. 520039413")
    ingest.add_argument("--from-year", type=int, required=True)
    ingest.add_argument("--to-year", type=int, required=True)
    ingest.add_argument("--archive", action="store_true")
    ingest.set_defaults(func=cmd_ingest)

    ingest_us = sub.add_parser("ingest-us", help="load one US company from SEC EDGAR")
    ingest_us.add_argument(
        "--cik", required=True, nargs="+", help="one or more SEC CIKs, e.g. 320193 789019"
    )
    # Six years is enough for a year-on-year comparison plus the history the
    # baseline needs to call a move unusual, without loading two decades of
    # filings nobody will read. It is an ingestion window, not a financial rule.
    ingest_us.add_argument("--from-year", type=int, default=2020)
    ingest_us.add_argument("--to-year", type=int, default=2026)
    ingest_us.add_argument("--archive", action="store_true")
    ingest_us.add_argument(
        "--publish", action="store_true", help="make it visible to the API straight away"
    )
    ingest_us.set_defaults(func=cmd_ingest_us)

    snapshots = sub.add_parser(
        "snapshots", help="rebuild stored analysis without calling a provider"
    )
    snapshots.add_argument(
        "--entity", nargs="*", help="limit to these provider entity ids (CIK or registrar number)"
    )
    snapshots.set_defaults(func=cmd_snapshots)

    quality = sub.add_parser(
        "quality", help="where the accounting identities do not close (development tool)"
    )
    quality.add_argument(
        "--all-periods", action="store_true", help="every stored period, not just the latest"
    )
    quality.add_argument(
        "--verbose-checks", action="store_true", help="list identities that held too"
    )
    quality.add_argument(
        "--strict", action="store_true", help="exit non-zero when anything is broken"
    )
    quality.add_argument("--entity", nargs="*", help="limit to these provider entity ids")
    quality.set_defaults(func=cmd_quality)

    metrics = sub.add_parser("metrics", help="computed metrics for one period, for hand checking")
    metrics.add_argument("--entity", required=True)
    metrics.add_argument("--year", type=int, required=True)
    metrics.add_argument("--quarter", type=int, required=True, choices=(1, 2, 3, 4))
    metrics.add_argument(
        "--cumulative", action="store_true", help="year to date rather than the quarter alone"
    )
    metrics.set_defaults(func=cmd_metrics)

    signals = sub.add_parser("signals", help="what the engine notices about a company")
    signals.add_argument("--entity", required=True)
    signals.add_argument("--quarters", type=int, default=16)
    signals.add_argument(
        "--core-only", action="store_true", help="only rules that fire for every company"
    )
    signals.set_defaults(func=cmd_signals)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
