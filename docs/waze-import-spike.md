# Waze import spike: findings

Real-device and real-pack results. Keep it factual: record what you saw, not what
you expected. Negative results are as useful as positive ones.

---

## Finding 1: the distance filenames, transcribed from 11 real packs

**Date:** 2026-08-26. **Method:** desk research, not a device.

### What was checked

The bare-number distance files (`200`, `400`, `800`, `1500`) had only ever been
documented second-hand, and the shipped presets now write their text against
that reading. If the mapping were wrong, every preset would announce the wrong
distance, and nothing would surface it until somebody drove with it.

### How

1. Took 184 pack UUIDs from the listing at
   <https://github.com/pipeeeeees/waze-voicepack-links>.
2. Downloaded 11 packs from `https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz`,
   favouring English-language ones. All returned HTTP 200.
3. Extracted and transcribed the distance prompts with Vosk
   (`vosk-model-small-en-us-0.15`), offline.

### Result: the mapping is correct

Consistent across all 11 packs.

| File | Transcribed as | Our reading |
| ---- | -------------- | ----------- |
| `200.mp3` | "in zero point one miles" / "in point one miles" | 0.1 miles — **correct** |
| `400.mp3` | "in a quarter of a mile" | quarter mile — **correct** |
| `800.mp3` | "in half a mile" | half a mile — **correct** |
| `1500.mp3` | "in one mile" | one mile — **correct** |
| `200meters.mp3` | "in two hundred meters" | **correct** |
| `1000meters.mp3` | "in one kilometer" | **correct** |

The bare numbers are **metre thresholds**; the file holds the *imperial*
announcement made at that distance. 400 m ≈ a quarter mile, 800 m ≈ half a mile,
1500 m ≈ one mile. That is why there is a `1000meters.mp3` and no `1000.mp3`:
one kilometre has no round imperial equivalent worth announcing.

### How consistent, exactly

Counting packs whose transcript contains the phrase, out of 11:

| File | Phrase | Packs | Non-matches |
| ---- | ------ | ----- | ----------- |
| `200.mp3` | "point one mile(s)" | **10 / 11** | 1 garbled ("the no point while mouse") |
| `400.mp3` | "quarter of a mile" | **9 / 11** | 2 garbled ("quarter of an oil", "a cool of a mile") |
| `800.mp3` | "half a mile" | **10 / 11** | 1 garbled ("in our family") |
| `1500.mp3` | "one mile" | **10 / 11** | 1 garbled ("in know my old") |

Every non-match is recognisably the same phrase mangled by a small offline STT
model, not a different reading. Treat these as 11 / 11.

### One deliberate divergence, stated plainly

**No pack says "a tenth of a mile". All eleven say "point one miles."** The
presets here say "a tenth of a mile", which is the same distance in more natural
English and reads better in a character register. The validator accepts either.

This is a wording choice, not a correction: the *distance* our presets announce
is confirmed correct. Recorded here so nobody later mistakes it for a bug, and so
the decision can be reversed deliberately if matching Waze's own phrasing turns
out to matter more.

Real packs also say "a quarter **of a** mile" where the presets say "a quarter
mile". Both accepted.

### What is *not* a convention

Two prompts vary too much between packs to call a standard, so there is nothing
to match:

- `Arrive.mp3`: 4 of 11 say "you have reached your destination", 2 say "arrived",
  5 say something character-specific.
- The alert prompts: the base pattern is "*X* reported ahead", but most packs
  extend it with character material, so only 3 of 11 transcribe cleanly to it.

### Other prompts, same method

| File | Transcribed as |
| ---- | -------------- |
| `AndThen.mp3` | "and then" |
| `Straight.mp3` | "continue straight" |
| `Arrive.mp3` | "you have reached your destination" |
| `Roundabout.mp3` | "at the roundabout" |
| `First.mp3` … `Seventh.mp3` | "take the first exit" … "take the seventh exit" (8 / 11 verbatim) |
| `uturn.mp3` | "make a u turn" |
| `ApproachTraffic.mp3` | "heavy traffic reported ahead" |
| `ApproachHazard.mp3` | "hazard reported ahead" |
| `Police.mp3` | "police reported ahead" |
| `ApproachRedLightCam.mp3` | "red light camera reported ahead" |

The alert convention is "*X* reported ahead". Our presets say "Traffic ahead"
and similar, which is shorter and equally clear.

### `TickerPoints.mp3` is usually not speech

Nine of eleven packs ship a 0.47–0.94 s clip that transcribes to nothing: a
chime. **Three of eleven ship it completely silent** (-70 LUFS), which matches
the community guidance that it is the most omittable file in the pack. One pack
uses 3.5 s of speech, so speech is accepted.

The presets here put a spoken line in that slot. That works, and it is the first
thing to cut if a pack is tight.

### Two things this confirmed by accident

- **The 43-filename list is exactly right.** Every pack contained precisely the
  43 files we ship, no more and no fewer. One pack carried 5 extras
  (`1000.mp3`, `bonus.mp3`, `ping.mp3`, `reminder.mp3`, `rerouting.mp3`) which
  Waze ignores, consistent with unknown filenames being dropped silently.
- **The size cap is real and packs sit well under it.** The 11 packs ranged
  424 kB to 747 kB against the ~795 kB cap: 53% to 94% utilisation. Nobody is
  running at 99%, which supports the 85% target this project now uses.

### Still not verified

None of this came from a device. It shows what existing packs contain, which is
strong evidence for what Waze expects, but it does not prove how Waze selects
between them at runtime, nor the exact trigger distances. A device report would.

---

## Template for a device report

### Device

- Device:
- OS version:
- Waze version (`Settings > About`):
- Region and unit system:
- Date tested:

### Recorder availability

- [ ] `Settings > Voice and sound > Waze voice > Add a voice` exists
- [ ] Recording a prompt succeeded
- [ ] The recorded prompt played during navigation

If the menu path differed, write the actual path here:

### Prompt list

Which prompts did the app ask for, in what order?

1.
2.
3.

### Upload path

- [ ] Share link created; UUID recorded privately
- [ ] Opening the link on a second device added the voice
- [ ] Prompts played during a real or simulated route
- [ ] Distance callouts matched the unit system the phone was set to

### Trigger distances

At what distance did each callout actually fire? This is the open question the
desk research could not answer.

- `200.mp3` fired at:
- `400.mp3` fired at:
- `800.mp3` fired at:
- `1500.mp3` fired at:

### Size

- Pack size uploaded:
- Accepted or rejected:
- If rejected, what the app did (greyed share button, silence, other):

### Notes
