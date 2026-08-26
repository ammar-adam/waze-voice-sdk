"""What Waze actually expects in a custom voice pack.

Sourced from the community archive at
https://github.com/pipeeeeees/waze-voicepack-links (``mp3_upload/valid_waze_filenames.txt``
and ``mp3_upload/file_compression.py``), plus the constraints reported in that
repository's discussion #31.

Two things here are not guessable and must not be guessed:

**The filenames.** Waze matches on exact filename. ``200.mp3`` is the 0.1 mile
callout, not "200 of something"; ``1500.mp3`` is one mile; ``TickerPoints.mp3``
is the reroute chime. Anything not on this list is silently ignored by the
server, so a typo does not raise an error, it just produces a pack missing that
prompt.

**The aggregate size budget.** Waze rejects a pack whose MP3s total more than
roughly 0.8 MB. The rejection is server-side and does not announce itself: the
share button greys out after saving, or the link works but plays silence on the
receiving device. That makes the budget the single most important thing to get
right before upload.
"""

from __future__ import annotations

from dataclasses import dataclass

# The community tooling targets 0.795 MB against a limit reported as "roughly
# 0.8 MB". Interpreting MB as decimal is the conservative reading, and the
# margin absorbs MP3 container overhead the encoder adds after allocation.
AGGREGATE_BUDGET_BYTES = 795_000

# Reserved out of the budget before allocating bitrates. ID3 headers, frame
# padding, and the encoder's own rounding all land on top of the theoretical
# bitrate-times-duration figure.
OVERHEAD_RESERVE_BYTES = 20_000

SHARE_LINK_TEMPLATE = "https://waze.com/ul?acvp={uuid}"
BACKUP_DOWNLOAD_TEMPLATE = "https://voice-prompts-ipv6.waze.com/{uuid}.tar.gz"

UNITS_ANY = "any"
UNITS_METRIC = "metric"
UNITS_IMPERIAL = "imperial"


@dataclass(frozen=True)
class WazeSlot:
    """One prompt slot in a Waze voice pack."""

    filename: str
    units: str
    meaning: str
    # Whether a pack is meaningfully broken without it. Waze itself accepts
    # incomplete packs: missing files produce warnings, not rejection, and the
    # app falls back to its default voice for anything absent.
    core: bool = False


# Ordered roughly as a driver hears them. The export step uses this order.
SLOTS: tuple[WazeSlot, ...] = (
    # -- start of drive ----------------------------------------------------
    WazeSlot("StartDrive1.mp3", UNITS_ANY, "Drive start greeting, variant 1", core=True),
    WazeSlot("StartDrive2.mp3", UNITS_ANY, "Drive start greeting, variant 2"),
    WazeSlot("StartDrive3.mp3", UNITS_ANY, "Drive start greeting, variant 3"),
    WazeSlot("StartDrive4.mp3", UNITS_ANY, "Drive start greeting, variant 4"),
    WazeSlot("StartDrive5.mp3", UNITS_ANY, "Drive start greeting, variant 5"),
    WazeSlot("StartDrive6.mp3", UNITS_ANY, "Drive start greeting, variant 6"),
    WazeSlot("StartDrive7.mp3", UNITS_ANY, "Drive start greeting, variant 7"),
    WazeSlot("StartDrive8.mp3", UNITS_ANY, "Drive start greeting, variant 8"),
    WazeSlot("StartDrive9.mp3", UNITS_ANY, "Drive start greeting, variant 9"),
    # -- distance callouts, imperial --------------------------------------
    # Readings below are transcribed from 11 real packs, not inferred. The bare
    # numbers are metre thresholds; the file holds the *imperial* announcement
    # made at that distance. See docs/waze-import-spike.md.
    WazeSlot("200.mp3", UNITS_IMPERIAL, 'In 0.1 miles ("zero point one miles")', core=True),
    WazeSlot("400.mp3", UNITS_IMPERIAL, 'In a quarter of a mile', core=True),
    WazeSlot("800.mp3", UNITS_IMPERIAL, "In half a mile", core=True),
    WazeSlot("1500.mp3", UNITS_IMPERIAL, "In one mile", core=True),
    # -- distance callouts, metric ----------------------------------------
    WazeSlot("200meters.mp3", UNITS_METRIC, "In 200 meters", core=True),
    WazeSlot("400meters.mp3", UNITS_METRIC, "In 400 meters", core=True),
    WazeSlot("800meters.mp3", UNITS_METRIC, "In 800 meters", core=True),
    WazeSlot("1000meters.mp3", UNITS_METRIC, "In 1000 meters", core=True),
    WazeSlot("1500meters.mp3", UNITS_METRIC, "In 1500 meters", core=True),
    # -- maneuvers ---------------------------------------------------------
    WazeSlot("TurnLeft.mp3", UNITS_ANY, "Turn left", core=True),
    WazeSlot("TurnRight.mp3", UNITS_ANY, "Turn right", core=True),
    WazeSlot("KeepLeft.mp3", UNITS_ANY, "Keep left", core=True),
    WazeSlot("KeepRight.mp3", UNITS_ANY, "Keep right", core=True),
    WazeSlot("ExitLeft.mp3", UNITS_ANY, "Exit left", core=True),
    WazeSlot("ExitRight.mp3", UNITS_ANY, "Exit right", core=True),
    WazeSlot("Straight.mp3", UNITS_ANY, "Continue straight", core=True),
    WazeSlot("uturn.mp3", UNITS_ANY, "Make a U-turn", core=True),
    WazeSlot("AndThen.mp3", UNITS_ANY, "Joins two consecutive instructions", core=True),
    WazeSlot("Arrive.mp3", UNITS_ANY, "You have arrived", core=True),
    # -- roundabouts -------------------------------------------------------
    WazeSlot("Roundabout.mp3", UNITS_ANY, "At the roundabout"),
    WazeSlot("First.mp3", UNITS_ANY, "Take the first exit"),
    WazeSlot("Second.mp3", UNITS_ANY, "Take the second exit"),
    WazeSlot("Third.mp3", UNITS_ANY, "Take the third exit"),
    WazeSlot("Fourth.mp3", UNITS_ANY, "Take the fourth exit"),
    WazeSlot("Fifth.mp3", UNITS_ANY, "Take the fifth exit"),
    WazeSlot("Sixth.mp3", UNITS_ANY, "Take the sixth exit"),
    WazeSlot("Seventh.mp3", UNITS_ANY, "Take the seventh exit"),
    # -- alerts ------------------------------------------------------------
    WazeSlot("ApproachTraffic.mp3", UNITS_ANY, "Traffic ahead"),
    WazeSlot("ApproachAccident.mp3", UNITS_ANY, "Accident reported ahead"),
    WazeSlot("ApproachHazard.mp3", UNITS_ANY, "Hazard ahead"),
    WazeSlot("ApproachSpeedCam.mp3", UNITS_ANY, "Speed camera ahead"),
    WazeSlot("ApproachRedLightCam.mp3", UNITS_ANY, "Red light camera ahead"),
    WazeSlot("Police.mp3", UNITS_ANY, "Police reported ahead"),
    # -- misc --------------------------------------------------------------
    # Usually a half-second chime rather than speech, and three of eleven real
    # packs ship it deliberately silent. Speech works, but it is the first
    # thing to drop when a pack is tight.
    WazeSlot("TickerPoints.mp3", UNITS_ANY, "Reroute chime. Safe to omit to save budget"),
)

VALID_FILENAMES: frozenset[str] = frozenset(slot.filename for slot in SLOTS)

BY_FILENAME: dict[str, WazeSlot] = {slot.filename: slot for slot in SLOTS}

# Export order, so the pack listing reads the way a drive sounds.
FILENAME_ORDER: dict[str, int] = {slot.filename: index for index, slot in enumerate(SLOTS)}


def slots_for_units(units: str) -> tuple[WazeSlot, ...]:
    """Slots that apply when the driver's app is set to ``units``.

    Distance callouts are two separate file sets. A pack carrying only one of
    them works in that unit system and falls back to the default Waze voice for
    distances in the other, which is jarring rather than broken.
    """
    if units not in (UNITS_METRIC, UNITS_IMPERIAL):
        raise ValueError(f"units must be {UNITS_METRIC!r} or {UNITS_IMPERIAL!r}, got {units!r}")
    return tuple(slot for slot in SLOTS if slot.units in (UNITS_ANY, units))


def core_filenames(units: str | None = None) -> set[str]:
    """Filenames a usable pack should carry.

    With ``units`` given, only that unit system's distance callouts count.
    Without it, both sets count, which is what a pack intended for anyone needs.
    """
    if units is None:
        return {slot.filename for slot in SLOTS if slot.core}
    return {slot.filename for slot in slots_for_units(units) if slot.core}


def is_valid(filename: str) -> bool:
    return filename in VALID_FILENAMES


def unknown_filenames(filenames: set[str]) -> set[str]:
    """Names Waze will silently ignore.

    Worth surfacing loudly: an ignored file is not an error anywhere in the
    upload path, it just quietly does not exist in the finished pack.
    """
    return filenames - VALID_FILENAMES
