"""Reading the five dimensions off one period's analysis.

Pure, and deliberately thin. Everything this decides was already decided: the
signals fired against thresholds settled in question D, and the metrics resolved
or did not. Report Pulse regroups that into the five questions a reader arrives
with (spec section 6.1) and adds no judgement of its own.

That thinness is what makes it defensible. A pulse band is a summary of the
findings below it, so a reader who distrusts the band can scroll down and check
every signal it was built from.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from financial_core.pulse.dimensions import (
    DIMENSIONS,
    PULSE_VERSION,
    PulseDimension,
    PulseState,
)
from financial_core.signals import Severity, Signal

# Severities that make a dimension read weak rather than merely worth watching.
_WEAKENING: Final[frozenset[Severity]] = frozenset({Severity.WARNING, Severity.CRITICAL})


@dataclass(frozen=True, slots=True)
class DimensionReading:
    """One dimension, this period."""

    code: str
    state: PulseState
    message_key: str
    signal_codes: tuple[str, ...]
    """The signals the state was read from. There is nothing else behind it."""
    version: str = PULSE_VERSION

    @property
    def is_concerning(self) -> bool:
        return self.state.is_concerning


@dataclass(frozen=True, slots=True)
class Pulse:
    """The five dimensions together."""

    readings: tuple[DimensionReading, ...]
    version: str = PULSE_VERSION

    @property
    def concerning(self) -> tuple[DimensionReading, ...]:
        return tuple(reading for reading in self.readings if reading.is_concerning)

    @property
    def readable(self) -> tuple[DimensionReading, ...]:
        """Dimensions the company reports enough to read at all."""
        return tuple(
            reading for reading in self.readings if reading.state is not PulseState.NO_DATA
        )


def read_dimension(
    dimension: PulseDimension,
    signals: Sequence[Signal],
    available_metrics: frozenset[str],
) -> DimensionReading:
    """Read one dimension from the signals that fired in it.

    A dimension with none of its metrics resolving is `no_data`, checked before
    anything else. Silence because nothing was measured is not silence because
    nothing moved, and reporting the first as "stable" would be the plainest
    possible breach of section 4.4.
    """
    if not available_metrics & set(dimension.metric_codes):
        return DimensionReading(
            code=dimension.code,
            state=PulseState.NO_DATA,
            message_key=dimension.message_key,
            signal_codes=(),
            version=dimension.version,
        )

    mine = [signal for signal in signals if signal.code in set(dimension.signal_codes)]
    codes = tuple(signal.code for signal in mine)

    if any(signal.severity in _WEAKENING for signal in mine):
        state = PulseState.WEAK
    elif any(signal.severity is Severity.WATCH for signal in mine):
        state = PulseState.WATCH
    elif any(signal.severity is Severity.POSITIVE for signal in mine):
        state = PulseState.STRONG
    else:
        # Informational signals do not move a dimension. A tax rate that ticked
        # up is worth saying and is not a change in how profitable the company
        # is, which is what its own rule already records.
        state = PulseState.STABLE

    return DimensionReading(
        code=dimension.code,
        state=state,
        message_key=dimension.message_key,
        signal_codes=codes,
        version=dimension.version,
    )


def read_pulse(
    signals: Sequence[Signal],
    available_metrics: frozenset[str],
    dimensions: Sequence[PulseDimension] = DIMENSIONS,
) -> Pulse:
    """The five dimensions, in the order section 6.1 lists them."""
    return Pulse(
        readings=tuple(
            read_dimension(dimension, signals, available_metrics) for dimension in dimensions
        )
    )
