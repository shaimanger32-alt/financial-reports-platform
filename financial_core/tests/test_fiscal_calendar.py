"""Classification against a company's own fiscal calendar.

The dates below are Apple's, taken from the SEC EDGAR company facts API rather
than composed. Apple's fiscal year is 52 or 53 weeks and ends on the last
Saturday of September, which is the shape that the calendar-year classifier
refused outright — correctly, since it had no way to know what those dates
meant.

The other half of these tests is that a calendar-year issuer still gets exactly
the answers it got before. Every Israeli company we hold closes on 31 December,
and a change to the period model that quietly moved one of their quarters would
be far more damaging than not supporting Apple at all.
"""

from datetime import date

import pytest

from financial_core.periods import (
    DurationKind,
    FiscalCalendar,
    FiscalYearWindow,
    PeriodKind,
    calendar_year_calendar,
    classify,
    classify_in,
)

# Apple Inc., as reported to the SEC.
APPLE = FiscalCalendar(
    (
        FiscalYearWindow(2024, date(2023, 10, 1), date(2024, 9, 28)),
        FiscalYearWindow(2025, date(2024, 9, 29), date(2025, 9, 27)),
        FiscalYearWindow(2026, date(2025, 9, 28), date(2026, 9, 26)),
    )
)

CALENDAR_YEARS = calendar_year_calendar(2022, 2026)


class TestApple:
    def test_the_fiscal_year_is_recognised(self) -> None:
        period = classify_in(date(2024, 9, 29), date(2025, 9, 27), APPLE)

        assert period is not None
        assert period.fiscal_year == 2025
        assert period.duration_kind is DurationKind.ANNUAL

    def test_the_first_quarter_ends_in_december(self) -> None:
        """2025-09-28 to 2025-12-27 is Apple's Q1 of fiscal 2026, and closes no
        calendar quarter at all."""
        period = classify_in(date(2025, 9, 28), date(2025, 12, 27), APPLE)

        assert period is not None
        assert (period.fiscal_year, period.fiscal_quarter) == (2026, 1)
        assert period.duration_kind is DurationKind.QUARTER

    def test_a_discrete_second_quarter(self) -> None:
        period = classify_in(date(2025, 12, 28), date(2026, 3, 28), APPLE)

        assert period is not None
        assert (period.fiscal_year, period.fiscal_quarter) == (2026, 2)
        assert period.duration_kind is DurationKind.QUARTER

    def test_the_cumulative_half_year_is_year_to_date(self) -> None:
        """Same end date as the discrete quarter above, different start. The
        pair is exactly what section 14.6 forbids mixing."""
        period = classify_in(date(2025, 9, 28), date(2026, 3, 28), APPLE)

        assert period is not None
        assert (period.fiscal_year, period.fiscal_quarter) == (2026, 2)
        assert period.duration_kind is DurationKind.YTD
        assert period.is_year_to_date

    def test_the_discrete_and_cumulative_quarters_do_not_collide(self) -> None:
        discrete = classify_in(date(2025, 12, 28), date(2026, 3, 28), APPLE)
        cumulative = classify_in(date(2025, 9, 28), date(2026, 3, 28), APPLE)

        assert discrete is not None and cumulative is not None
        assert discrete.code != cumulative.code

    def test_a_balance_sheet_date_that_closes_no_calendar_quarter(self) -> None:
        """The old classifier rejected this, discarding the balance sheet."""
        period = classify_in(None, date(2025, 12, 27), APPLE)

        assert period is not None
        assert (period.fiscal_year, period.fiscal_quarter) == (2026, 1)
        assert period.period_kind is PeriodKind.INSTANT

    def test_the_old_classifier_really_did_reject_it(self) -> None:
        """Guards the reason this module exists."""
        assert classify(date(2025, 9, 28), date(2025, 12, 27)) is None
        assert classify(None, date(2025, 12, 27)) is None


class TestCalendarYearIssuersAreUnchanged:
    @pytest.mark.parametrize(
        ("start", "end", "quarter", "kind"),
        [
            (date(2025, 1, 1), date(2025, 3, 31), 1, DurationKind.QUARTER),
            (date(2025, 4, 1), date(2025, 6, 30), 2, DurationKind.QUARTER),
            (date(2025, 7, 1), date(2025, 9, 30), 3, DurationKind.QUARTER),
            (date(2025, 10, 1), date(2025, 12, 31), 4, DurationKind.QUARTER),
            (date(2025, 1, 1), date(2025, 6, 30), 2, DurationKind.YTD),
            (date(2025, 1, 1), date(2025, 9, 30), 3, DurationKind.YTD),
            (date(2025, 1, 1), date(2025, 12, 31), 4, DurationKind.ANNUAL),
        ],
    )
    def test_matches_the_calendar_year_classifier(
        self, start: date, end: date, quarter: int, kind: DurationKind
    ) -> None:
        period = classify_in(start, end, CALENDAR_YEARS)
        original = classify(start, end)

        assert period is not None and original is not None
        assert period.fiscal_quarter == quarter
        assert period.duration_kind is kind
        assert period.code == original.code

    def test_instants_agree_on_their_fiscal_position(self) -> None:
        for month, day, quarter in ((3, 31, 1), (6, 30, 2), (9, 30, 3), (12, 31, 4)):
            period = classify_in(None, date(2025, month, day), CALENDAR_YEARS)
            assert period is not None
            assert (period.fiscal_year, period.fiscal_quarter) == (2025, quarter)


class TestRefusingToGuess:
    def test_a_date_outside_every_declared_year_is_unclassified(self) -> None:
        """Boundaries we were not told about are not invented."""
        assert classify_in(None, date(2019, 6, 30), APPLE) is None

    def test_an_empty_calendar_classifies_nothing(self) -> None:
        assert classify_in(None, date(2025, 12, 27), FiscalCalendar(())) is None

    def test_a_window_spanning_two_fiscal_years_is_unclassified(self) -> None:
        assert classify_in(date(2024, 9, 1), date(2025, 3, 29), APPLE) is None

    def test_a_reversed_window_is_unclassified(self) -> None:
        assert classify_in(date(2026, 3, 28), date(2025, 12, 28), APPLE) is None

    def test_windows_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="ordered oldest first"):
            FiscalCalendar(
                (
                    FiscalYearWindow(2025, date(2024, 9, 29), date(2025, 9, 27)),
                    FiscalYearWindow(2024, date(2023, 10, 1), date(2024, 9, 28)),
                )
            )

    def test_a_fiscal_year_cannot_end_before_it_starts(self) -> None:
        with pytest.raises(ValueError, match="cannot end before it starts"):
            FiscalYearWindow(2025, date(2025, 9, 27), date(2024, 9, 29))


class TestFiftyThreeWeekYears:
    """A 53-week year stretches its own quarters rather than breaking them."""

    def test_the_extra_week_does_not_shift_the_quarter(self) -> None:
        # 2023-10-01 to 2024-09-28 is 364 days; a 53-week year is 371.
        long_year = FiscalCalendar((FiscalYearWindow(2023, date(2022, 9, 25), date(2023, 9, 30)),))
        period = classify_in(date(2022, 9, 25), date(2023, 9, 30), long_year)

        assert period is not None
        assert period.fiscal_quarter == 4
        assert period.duration_kind is DurationKind.ANNUAL
        assert period.days == 371
