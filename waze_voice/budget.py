"""Fitting a voice pack inside Waze's aggregate size budget.

Waze rejects packs whose MP3s total more than roughly 0.8 MB, and rejects them
silently. So the question is not "does this encode" but "how should a fixed
number of bytes be divided between forty-odd clips".

The community tooling answers that with one bitrate for everything, found by
binary search. That is safe and simple, and it is also leaving quality on the
table: it spends the same bits per second on a nine-second drive-start greeting
you hear once as on "turn left", which you hear on every single turn.

The default strategy here allocates per clip instead.

## Where the allocation rule comes from

Perceived quality rises with bitrate but saturates, so model a clip's quality as
proportional to ``log(bitrate)``. Weight each clip by how much its quality
matters, ``w``, and maximise

    sum over i of  w_i * log(b_i)      subject to      sum of b_i * d_i <= B

where ``d`` is duration and ``B`` the budget in bits. Setting the Lagrangian
derivative to zero gives

    b_i = lambda * w_i / d_i

**Bitrate proportional to weight over duration.** Short clips get more bits per
second than long ones, and important clips get more than incidental ones, which
is exactly the intuition, but with a defensible scale rather than a guess.

Substituting back, the multiplier has a closed form: since
``sum(b_i * d_i) = lambda * sum(w_i)``, we get ``lambda = B / sum(w_i)``. No
search required. Clamping is then handled by fixing whichever clips hit a bound
and re-solving for the rest, the same shape as water-filling.

## Why bitrates are snapped to a ladder

MP3 constant bitrate is not continuous. At 44.1 kHz, MPEG-1 Layer III allows
32 kbps and up; below that the file has to drop to 22.05 kHz and MPEG-2, which
for speech is a good trade rather than a compromise, since almost nothing in a
navigation prompt lives above 11 kHz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

# MPEG-1 Layer III at 44.1 kHz.
MPEG1_BITRATES: tuple[int, ...] = (32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
# MPEG-2 Layer III at 22.05 kHz, which is where sub-32 kbps becomes available.
MPEG2_BITRATES: tuple[int, ...] = (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)

SAMPLE_RATE_FULL = 44100
SAMPLE_RATE_LOW = 22050

STRATEGY_WEIGHTED = "weighted"
STRATEGY_UNIFORM = "uniform"
STRATEGIES = (STRATEGY_WEIGHTED, STRATEGY_UNIFORM)

POLICY_AUTO = "auto"
POLICY_FIXED = "fixed"
SAMPLE_RATE_POLICIES = (POLICY_AUTO, POLICY_FIXED)


@dataclass(frozen=True)
class ClipSpec:
    """A clip competing for a share of the budget."""

    filename: str
    source: Path
    duration: float
    weight: float = 1.0


@dataclass
class Allocation:
    filename: str
    source: Path
    duration: float
    weight: float
    bitrate_kbps: int
    sample_rate: int
    actual_bytes: int | None = None
    bound: str = ""  # "min", "max", or "" when the solver chose freely

    @property
    def predicted_bytes(self) -> int:
        return int(self.bitrate_kbps * 1000 * self.duration / 8)

    @property
    def bytes(self) -> int:
        """Measured size when available, predicted otherwise."""
        return self.actual_bytes if self.actual_bytes is not None else self.predicted_bytes


@dataclass
class AllocationPlan:
    allocations: list[Allocation] = field(default_factory=list)
    budget_bytes: int = 0
    strategy: str = STRATEGY_WEIGHTED
    notes: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(item.bytes for item in self.allocations)

    @property
    def total_predicted_bytes(self) -> int:
        return sum(item.predicted_bytes for item in self.allocations)

    @property
    def total_duration(self) -> float:
        return sum(item.duration for item in self.allocations)

    @property
    def headroom_bytes(self) -> int:
        return self.budget_bytes - self.total_bytes

    @property
    def fits(self) -> bool:
        return self.total_bytes <= self.budget_bytes

    @property
    def utilisation(self) -> float:
        if self.budget_bytes <= 0:
            return 0.0
        return self.total_bytes / self.budget_bytes

    def get(self, filename: str) -> Allocation | None:
        for item in self.allocations:
            if item.filename == filename:
                return item
        return None

    def in_size_order(self) -> list[Allocation]:
        return sorted(self.allocations, key=lambda item: item.bytes, reverse=True)


def ladder_for(sample_rate: int) -> tuple[int, ...]:
    return MPEG2_BITRATES if sample_rate == SAMPLE_RATE_LOW else MPEG1_BITRATES


def snap_down(bitrate: float, ladder: tuple[int, ...]) -> int:
    """Largest ladder value not above ``bitrate``. Rounding down keeps the sum under budget."""
    candidates = [value for value in ladder if value <= bitrate]
    return candidates[-1] if candidates else ladder[0]


def next_lower(bitrate: int, ladder: tuple[int, ...]) -> int | None:
    lower = [value for value in ladder if value < bitrate]
    return lower[-1] if lower else None


def _resolve_sample_rate(bitrate: float, policy: str) -> tuple[int, tuple[int, ...]]:
    """Pick a sample rate for a target bitrate, and the ladder that goes with it."""
    if policy == POLICY_FIXED or bitrate >= MPEG1_BITRATES[0]:
        return SAMPLE_RATE_FULL, MPEG1_BITRATES
    # Below 32 kbps, 44.1 kHz is not available at all in MPEG-1. Dropping to
    # 22.05 kHz both unlocks the lower rungs and spends the remaining bits on
    # the band speech actually occupies.
    return SAMPLE_RATE_LOW, MPEG2_BITRATES


def allocate(
    clips: list[ClipSpec],
    *,
    budget_bytes: int,
    strategy: str = STRATEGY_WEIGHTED,
    min_kbps: int = 24,
    max_kbps: int = 128,
    sample_rate_policy: str = POLICY_AUTO,
) -> AllocationPlan:
    """Divide ``budget_bytes`` between ``clips``.

    ``min_kbps`` defaults to 24 rather than the encoder floor: below about
    32 kbps speech starts to sound obviously degraded, and the community
    guidance is that under 32 kbps quality falls off sharply. The floor is a
    quality decision, not a technical one, so it is configurable.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}, got {strategy!r}")
    if sample_rate_policy not in SAMPLE_RATE_POLICIES:
        raise ValueError(f"sample_rate_policy must be one of {SAMPLE_RATE_POLICIES}")

    plan = AllocationPlan(budget_bytes=budget_bytes, strategy=strategy)
    usable = [clip for clip in clips if clip.duration > 0]
    if not usable:
        return plan

    if strategy == STRATEGY_UNIFORM:
        return _allocate_uniform(
            usable, budget_bytes, min_kbps, max_kbps, sample_rate_policy, plan
        )
    return _allocate_weighted(usable, budget_bytes, min_kbps, max_kbps, sample_rate_policy, plan)


def _solve_at(
    clips: list[ClipSpec],
    multiplier: float,
    min_kbps: int,
    max_kbps: int,
    policy: str,
) -> list[Allocation]:
    """Allocate every clip at a given multiplier, clamped and snapped to a ladder."""
    solved: list[Allocation] = []
    for clip in clips:
        raw_kbps = (multiplier * clip.weight / clip.duration) / 1000.0

        bound = ""
        if raw_kbps > max_kbps:
            raw_kbps, bound = float(max_kbps), "max"
        elif raw_kbps < min_kbps:
            raw_kbps, bound = float(min_kbps), "min"

        sample_rate, ladder = _resolve_sample_rate(raw_kbps, policy)
        bitrate = snap_down(raw_kbps, ladder)
        bitrate = max(min(bitrate, max_kbps), ladder[0])

        solved.append(
            Allocation(
                filename=clip.filename,
                source=clip.source,
                duration=clip.duration,
                weight=clip.weight,
                bitrate_kbps=bitrate,
                sample_rate=sample_rate,
                bound=bound,
            )
        )
    return solved


def _allocate_weighted(
    clips: list[ClipSpec],
    budget_bytes: int,
    min_kbps: int,
    max_kbps: int,
    policy: str,
    plan: AllocationPlan,
) -> AllocationPlan:
    """Find the largest multiplier whose allocation still fits the budget.

    The closed form for lambda only holds while no clip is clamped. Once some
    are pinned to the floor or the ceiling, and once every rate is snapped to a
    discrete ladder, it stops being exact.

    Bisecting on lambda instead sidesteps all of that. Total size is monotonic
    in lambda, so the largest feasible value is what bisection converges on, and
    clamping and snapping are just part of evaluating a candidate. It also
    avoids a subtle failure of the freeze-as-you-go approach: a clip pinned to
    the floor early, while the budget still looked tight, never got revisited
    once other clips hit the ceiling and freed room up.
    """
    if budget_bytes <= 0:
        plan.notes.append("No budget available; every clip pinned to the minimum bitrate.")
        plan.allocations = _solve_at(clips, 0.0, min_kbps, max_kbps, policy)
        plan.allocations.sort(key=lambda item: item.filename)
        return plan

    def total_bytes(multiplier: float) -> int:
        return sum(item.predicted_bytes for item in _solve_at(clips, multiplier, min_kbps, max_kbps, policy))

    # Upper bound: comfortably past the point where every clip is at max_kbps.
    longest = max(clip.duration for clip in clips)
    smallest_weight = min((clip.weight for clip in clips if clip.weight > 0), default=1.0)
    high = max_kbps * 1000.0 * longest / smallest_weight * 2.0
    low = 0.0

    if total_bytes(high) <= budget_bytes:
        # Budget is not the binding constraint; max_kbps is.
        low = high
    else:
        for _ in range(64):
            mid = (low + high) / 2.0
            if total_bytes(mid) <= budget_bytes:
                low = mid
            else:
                high = mid

    plan.allocations = _solve_at(clips, low, min_kbps, max_kbps, policy)
    plan.allocations.sort(key=lambda item: item.filename)

    if plan.total_predicted_bytes > budget_bytes:
        # Only reachable when every clip is already at the floor.
        plan.notes.append(
            "Even at the minimum bitrate this pack exceeds the budget. Shorten "
            "the longest clips or drop optional prompts."
        )
    return plan


def _allocate_uniform(
    clips: list[ClipSpec],
    budget_bytes: int,
    min_kbps: int,
    max_kbps: int,
    policy: str,
    plan: AllocationPlan,
) -> AllocationPlan:
    """One bitrate for everything: what the community tooling does.

    Kept as a comparison baseline and an escape hatch. The export step reports
    both totals so the difference is visible rather than asserted.
    """
    total_duration = sum(clip.duration for clip in clips)
    ladder = MPEG1_BITRATES if policy == POLICY_FIXED else MPEG2_BITRATES

    chosen = ladder[0]
    for candidate in ladder:
        if candidate > max_kbps:
            break
        predicted = candidate * 1000 * total_duration / 8
        if predicted <= budget_bytes:
            chosen = candidate

    chosen = max(chosen, min(min_kbps, max_kbps))
    sample_rate, _ = _resolve_sample_rate(float(chosen), policy)

    for clip in clips:
        plan.allocations.append(
            Allocation(
                filename=clip.filename,
                source=clip.source,
                duration=clip.duration,
                weight=clip.weight,
                bitrate_kbps=chosen,
                sample_rate=sample_rate,
            )
        )
    plan.allocations.sort(key=lambda item: item.filename)
    return plan


def reduce_to_fit(plan: AllocationPlan, *, min_kbps: int = 24) -> Allocation | None:
    """Step one clip down a rung, choosing the one that costs the least quality.

    Called after encoding, when measured sizes have overshot the prediction.
    The clip picked is the one with the worst bytes-per-unit-weight ratio: the
    most expensive thing in the pack relative to how much it matters. Returns
    the clip that changed, or None when nothing can be reduced further.
    """
    candidates = []
    for item in plan.allocations:
        ladder = ladder_for(item.sample_rate)
        lower = next_lower(item.bitrate_kbps, ladder)
        if lower is None or lower < min_kbps:
            continue
        weight = item.weight if item.weight > 0 else 0.001
        candidates.append((item.bytes / weight, item, lower))

    if not candidates:
        return None

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    _, item, lower = candidates[0]
    item.bitrate_kbps = lower
    item.actual_bytes = None  # invalidated; the caller re-encodes
    return item
