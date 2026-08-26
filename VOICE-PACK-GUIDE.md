# Voice pack guide

Building a pack, start to finish.

## 0. Building more than one voice?

Make a pack per voice and pass `--pack` to everything:

```powershell
python scripts\wvs.py pack new my-voice --label "My voice"
python scripts\wvs.py run --pack my-voice
```

Each pack keeps its own source list, clips, and export under `packs/<name>/`, so
two voices never mix. Everything below happens inside a pack. Building only one
voice? Ignore packs and use the shared `audio/` tree.

## 1. Pick a voice you can actually use

Start with audio you have the right to use, and to redistribute if you plan to publish
anything. Your own voice, someone who gave explicit permission, public-domain or
permissively licensed material, or synthetic voices with clear rights.

Do not use copyrighted characters, actors, or celebrity voices without permission. See
[LEGAL.md](LEGAL.md).

## 2. Decide what the pack says

[config/phrases.json](config/phrases.json) is the inventory. Each entry:

| Field | Meaning |
| ----- | ------- |
| `id` | Stable machine-readable prompt ID. Used in filenames and routes. |
| `label` | Human-readable phrase, shown in checklists. |
| `required` | Whether the pack is incomplete without it. |
| `filename` | Final filename in `audio/master`. |
| `status` | `missing`, `sourced`, `extracted`, `cleaned`, `synthesized`, or `final`. Maintained by the pipeline. |
| `waze_filename` | The exact name Waze expects, e.g. `TurnLeft.mp3`. Validated against Waze's list. |
| `units` | `any`, `metric`, or `imperial`. Distance callouts are two separate file sets. |
| `weight` | This prompt's share of the pack size budget. Higher means more bitrate. |
| `group` | `start`, `distance`, `maneuver`, `lane`, `roundabout`, `arrival`, `alert`, or `misc`. |
| `order` | Position within the group. |
| `tts_text` | What synthesis should say, when it differs from the label. |
| `notes` | Production notes. |
| `aliases` | Alternative wordings, for your own reference. |

The shipped list covers all 43 prompts Waze recognises. You do not need every one: Waze
falls back to its default voice for anything absent, and dropping prompts you will never
hear is the easiest way to free up size budget.

## 3. Find your clips

Listen through your source media and note where each phrase occurs. Copy the sample CSV
and fill it in:

```powershell
copy data\sources.sample.csv data\my-sources.csv
```

```csv
phrase_id,source_path,start,end,take,preferred,gain_db,notes
turn_left,C:\media\episode-one.m4a,00:12:03.100,00:12:04.250,1,,,first attempt
turn_left,C:\media\episode-one.m4a,00:41:55.000,00:41:56.100,2,1,,cleaner delivery
```

Using a pack? Its `packs/<name>/sources.csv` already exists with the right
header and is picked up automatically, so there is nothing to copy.

Practical advice:

- **Grab several takes.** Cheap to note, and you will not know which one works until you
  hear it in a route. Mark the winner with `preferred=1` later.
- **Be generous with the boundaries.** Include a little air on each side; silence trimming
  tidies it up, and a syllable cut short cannot be recovered.
- **Prefer lines said in isolation.** A phrase over music can be rescued by Demucs, but a
  clean one never needs rescuing.
- **Watch the tone.** A line delivered as a question sounds wrong as a turn instruction,
  however clean the audio is.
- Rows are validated before any ffmpeg runs, so a typo fails immediately.

## 4. Run the pipeline

```powershell
python scripts\wvs.py run --sources data\my-sources.csv
```

Or step by step, which is what you will want while iterating:

```powershell
python scripts\wvs.py extract --sources data\my-sources.csv
python scripts\wvs.py clean --mode demucs
python scripts\wvs.py synth --accept-voice-terms
python scripts\wvs.py normalize
python scripts\wvs.py validate
```

Steps skip work that already exists; add `--force` to redo it.

## 5. Fill the gaps

Some phrases will not exist in your source. Three options:

- **Synthesize them** in your own voice: `python scripts\wvs.py synth`. See
  [docs/tts.md](docs/tts.md).
- **Record them yourself** and drop the file into `audio/extracted/` as
  `<phrase_id>__take1.wav`.
- **Leave them.** Waze falls back to its default voice for anything absent, and the export
  checklist lists what is missing.

## 6. Listen to it as a route

The step most people skip, and the one that catches the problems.

```powershell
python scripts\wvs.py qa
python scripts\wvs.py qa --route highway_merge
python scripts\wvs.py qa --list-routes
```

Playback chains phrases the way Waze does, so you hear "In a quarter mile, turn right" as
one instruction, and `AndThen` joining two maneuvers. Mark each one pass or fail; verdicts
are saved to `audio/qa-report.json`.

What to listen for:

- A prompt noticeably louder or quieter than its neighbours. Normalization should prevent
  this; if one stands out, check whether validation flagged it as an outlier.
- Clipped first or last syllables.
- Two chained phrases that do not flow, usually a distance clip with too much trailing air.
- Synthesized lines that are subtly too slow. Genuinely irritating at speed.

For the real test, render the route and play it in the car:

```powershell
python scripts\wvs.py qa --render route.wav --bed road-noise.wav
```

## 7. Export and upload

```powershell
python scripts\wvs.py export
```

This builds `audio/export/pack/`: MP3s named exactly as Waze expects, covering both metric
and imperial distance callouts, with bitrates allocated so the whole pack fits Waze's
0.8 MB aggregate limit. The step prints the total against that limit:

```
Pack total: 793.5 kB of 795.0 kB (99.8%) - within budget
```

If it says over budget, fix that before uploading. Waze rejects oversized packs silently:
the share button greys out, or the pack downloads and plays nothing. `HOW-TO-UPLOAD.md` in
the export folder lists what to cut, cheapest first. Quick wins: drop `TickerPoints.mp3`,
drop roundabout ordinals you will never hear, or export a single unit system:

```powershell
python scripts\wvs.py export --units metric
```

Then upload `audio/export/pack/` with the community tool at
<https://github.com/pipeeeeees/waze-voicepack-links>, keep the UUID it returns, and open
`https://waze.com/ul?acvp=<UUID>` on your phone.

Prefer not to use third-party tooling? The in-app recorder still works, at the cost of
audio quality, and `python scripts\record_assist.py` walks the prompt list for you.

Full detail in [docs/waze-import-workflow.md](docs/waze-import-workflow.md).

## 8. Iterate

Nothing here is one-shot. Fix a phrase and re-run just that phrase:

```powershell
python scripts\wvs.py extract --only turn_left --force --sources data\my-sources.csv
python scripts\wvs.py clean --only turn_left --force
python scripts\wvs.py normalize --only turn_left --force
python scripts\wvs.py qa
```

## Keeping the repo clean

Your media, clips, manifests, datasets, and model weights are all Git-ignored. Keep it
that way. `git status` before pushing.
