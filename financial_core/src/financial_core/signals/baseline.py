"""What normal looks like for this company.

Spec section 17 sets the order of preference for deciding whether a move is
material: a defined magnitude first, then **the company against its own
history**, then consistency across periods, and peer medians only once there is
enough coverage to build them.

The second of those needs no invented constant, which is why it carries most of
the weight here. A company whose collection period swings fifteen days every
quarter has not told you anything by swinging fifteen days again. The same move
at a company that has never varied by more than three is worth a look.

Median and median absolute deviation are used rather than mean and standard
deviation. Financial series are short and contain genuine one-off events, and a
single acquisition would inflate a standard deviation enough to hide everything
that followed.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

# Below this many observations, "normal" is a guess. Four quarters is one full
# seasonal cycle and the least that can describe a year.
MINIMUM_OBSERVATIONS: Final[int] = 4

# Scales median absolute deviation so it is comparable to a standard deviation
# on normally distributed data. Standard constant, not a tuning knob.
MAD_TO_SIGMA: Final[float] = 1.4826

# Guards against a company whose history is perfectly flat, where any deviation
# would otherwise divide by zero and read as infinite.
MINIMUM_SPREAD: Final[float] = 1e-9


@dataclass(frozen=True, slots=True)
class Baseline:
    """A company's own norm for one metric."""

    median: float
    spread: float
    """Median absolute deviation, scaled to be read like a standard deviation."""
    observations: int

    @property
    def is_reliable(self) -> bool:
        """Whether there is enough history to call anything unusual."""
        return self.observations >= MINIMUM_OBSERVATIONS

    def deviation_of(self, value: float) -> float | None:
        """How far a value sits from the norm, in robust units.

        Returns None when the history is too short to support the judgement, so
        a caller cannot accidentally treat two observations as a baseline.
        """
        if not self.is_reliable:
            return None
        if self.spread < MINIMUM_SPREAD:
            # A perfectly flat history. Any change is a departure, but the size
            # of it cannot be expressed in units of a spread that is zero.
            return 0.0 if value == self.median else None
        return (value - self.median) / self.spread


def build_baseline(history: Sequence[float]) -> Baseline | None:
    """Summarise a company's own history of one metric.

    The current period is not part of its own baseline; callers pass prior
    periods only. Including the value being judged would drag the norm toward it
    and mute exactly the move worth noticing.
    """
    values = [value for value in history if value is not None]
    if not values:
        return None

    median = statistics.median(values)
    absolute_deviations = [abs(value - median) for value in values]
    spread = statistics.median(absolute_deviations) * MAD_TO_SIGMA

    return Baseline(median=median, spread=spread, observations=len(values))


def consecutive_run(values: Sequence[float | None], predicate: object) -> int:
    """How many of the most recent periods in a row satisfy a condition.

    Spec section 14.4: a signal from a single quarter carries low confidence
    unless the magnitude is extreme. Persistence is how that gets measured.
    """
    assert callable(predicate)
    run = 0
    for value in reversed(values):
        if value is None or not predicate(value):
            break
        run += 1
    return run
