from datetime import UTC, datetime

from ion_pulse.api.routes.publications import journal_candidate_period


def test_candidate_period_includes_selected_and_previous_month() -> None:
    start, end = journal_candidate_period("2026-09", datetime(2026, 9, 8, tzinfo=UTC))

    assert start == datetime(2026, 8, 1, tzinfo=UTC)
    assert end == datetime(2026, 10, 1, tzinfo=UTC)


def test_candidate_period_crosses_year_boundary() -> None:
    start, end = journal_candidate_period("2026-01", datetime(2026, 1, 15, tzinfo=UTC))

    assert start == datetime(2025, 12, 1, tzinfo=UTC)
    assert end == datetime(2026, 2, 1, tzinfo=UTC)
