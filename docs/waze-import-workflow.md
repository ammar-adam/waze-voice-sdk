# Getting a pack into Waze

## How it actually works

The creation device and the consumption device are decoupled. Waze stores custom voice
packs **on its servers**, not on the phone, and distributes them as share links. So the
pack is built on a PC, uploaded, and then pulled down by whatever phone opens the link.

```
your MP3s  ->  upload  ->  Waze servers  ->  share link  ->  phone opens link  ->  pack installed
                                             waze.com/ul?acvp=<UUID>
```

Two facts follow from that, and both are useful:

- **The mobile app being record-only does not matter.** There is no MP3 upload in the
  Waze app on iOS or Android, and there is no point looking for one. The upload happens
  elsewhere.
- **Any pack can be retrieved.** Given a UUID, the pack downloads as a tarball from
  `https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz`. That is how you back up your own
  pack, and how you can inspect how an existing pack is built.

The community tooling that performs the upload lives at
<https://github.com/pipeeeeees/waze-voicepack-links> (see `mp3_upload/`). This SDK
produces the directory that tool expects: correct filenames, both unit systems, and
already inside the size budget.

An older method using a rooted Android emulator to swap files in
`custom_prompts_temp` is deprecated and is documented in that repository's
discussion #31. It is not needed and Waze has progressively made it harder.

## The two things that fail silently

### Filenames

Waze matches prompts by exact filename. Anything it does not recognise is **ignored
without an error**, so a near-miss produces a pack that is quietly missing that prompt.

The names are not guessable:

| File | What it actually is |
| ---- | ------------------- |
| `200.mp3` | "In 0.1 miles" - **imperial**, despite the name |
| `400.mp3` | "In a quarter mile" |
| `800.mp3` | "In half a mile" |
| `1500.mp3` | "In one mile" |
| `200meters.mp3` ... `1500meters.mp3` | The metric set, five files |
| `AndThen.mp3` | Joins two chained instructions |
| `TickerPoints.mp3` | The reroute chime |
| `StartDrive1-9.mp3` | Nine drive-start greetings, chosen at random |
| `First.mp3` ... `Seventh.mp3` | Roundabout exit ordinals |
| `uturn.mp3` | Lowercase, unlike everything else |

The authoritative list of all 43 lives in
[`waze_voice/wazepack.py`](../waze_voice/wazepack.py), transcribed from
`mp3_upload/valid_waze_filenames.txt` upstream. `config/phrases.json` carries the mapping
from our phrase IDs to those names, and the validator rejects a name Waze would not
recognise rather than letting it reach a pack.

### Metric and imperial are separate file sets

They are not alternatives; they are two independent sets of distance callouts. A pack
carrying only one works in that unit system and **falls back to the default Waze voice**
for distances in the other, mid-drive, which is more jarring than it sounds.

`wvs validate` reports coverage for both systems separately. Export both unless the budget
forces a choice:

```powershell
python scripts\wvs.py export --units metric
```

### The aggregate size limit

**Roughly 0.8 MB across every MP3 in the pack**, enforced server-side, with no error
message. Two symptoms:

- The share button greys out immediately after saving.
- The link works, the pack downloads, and every prompt plays silence.

Neither says "too big". This is the single most common reason a pack fails.

This SDK targets 795,000 bytes and prints the finished total against that budget before
you upload:

```
Pack total: 793.5 kB of 795.0 kB (99.8%) - within budget
```

If it says over budget, the export step exits non-zero and `HOW-TO-UPLOAD.md` in the
export folder lists what to cut, cheapest first.

## Bitrate allocation

The community guidance is 48 kbps constant across the pack, found by binary search. That
works, and it spends the same bits per second on a nine-second greeting you hear once as
on "turn left", which you hear on every turn.

This SDK allocates per clip instead, with bitrate proportional to **weight over
duration**. Short, frequently heard clips get more; long, rarely heard ones get less. Each
phrase carries a `weight` in `config/phrases.json`, and the derivation is in
[`waze_voice/budget.py`](../waze_voice/budget.py).

On a full 43-prompt pack the difference is roughly 12 percentage points of budget
utilisation, all of it spent on the prompts you actually hear. The uniform strategy is
still available for comparison:

```powershell
python scripts\wvs.py export --strategy uniform
```

Below 32 kbps, MP3 has no rungs at 44.1 kHz, so clips allocated less than that drop to
22.05 kHz. For speech that is a good trade rather than a compromise. Set
`export.sample_rate_policy` to `fixed` to keep everything at 44.1 kHz.

## Doing it

```powershell
python scripts\wvs.py run --sources data\my-sources.csv
python scripts\wvs.py qa
python scripts\wvs.py export
```

Then:

1. Read `audio/export/HOW-TO-UPLOAD.md`.
2. Upload `audio/export/pack/` with the community tool.
3. Keep the UUID it returns. It is the only handle on the pack.
4. Open `https://waze.com/ul?acvp=<UUID>` on the phone.
5. Select the voice under `Settings > Voice and sound`.
6. Drive or simulate a route.

### What to check on the device

One route exercises most of what can be wrong:

- A distance callout chained onto a maneuver. That is two files and the join between them.
- An arrival prompt.
- If your phone is set to metric, a metric route; if imperial, an imperial one. A pack
  missing one set will not tell you.

## If you would rather not upload

The in-app recorder still works:
`Settings > Voice and sound > Waze voice > Add a voice`. It needs no third-party tooling,
and it captures through the phone microphone and compresses hard, so expect noticeably
worse audio than uploading the files. `scripts/record_assist.py` walks the prompt list and
plays each clip on a keypress.

## Reporting findings

Device, OS version, Waze version, date, what you did, what happened. Into
[waze-import-spike.md](waze-import-spike.md). Negative results are worth writing down too.
