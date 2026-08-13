"""Report Pulse (spec section 6.1).

Five dimensions, each read off the signals that already fired in it. It adds no
threshold and no judgement of its own — a band is a summary of the findings
below it, so a reader who distrusts one can scroll down and check every signal
it was built from.
"""

from financial_core.pulse.dimensions import (
    DIMENSIONS,
    DIMENSIONS_BY_CODE,
    PULSE_VERSION,
    PulseDimension,
    PulseState,
)
from financial_core.pulse.engine import DimensionReading, Pulse, read_dimension, read_pulse

__all__ = [
    "DIMENSIONS",
    "DIMENSIONS_BY_CODE",
    "PULSE_VERSION",
    "DimensionReading",
    "Pulse",
    "PulseDimension",
    "PulseState",
    "read_dimension",
    "read_pulse",
]
