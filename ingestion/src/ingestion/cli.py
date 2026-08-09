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

from ingestion.archive import RawArchive
from ingestion.config import get_ingestion_settings
from ingestion.core_concepts import CORE_CONCEPTS
from ingestion.providers.base import FactQuery, ProviderFact
from ingestion.providers.magna_xbrl import MagnaXbrlClient, distinct_filings, find_conflicts

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
