# Waze Voice SDK

[![CI](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Character voices for Waze navigation.

## Just want the voices?

Open one of these on your phone, with Waze installed. It adds the voice. Then
`Settings > Voice and sound` and pick it. Nothing to install, no account.

| Voice | | |
| ----- | - | - |
| **Pooh** — warm, unhurried, audibly thinking it through | [Add to Waze](https://waze.com/ul?acvp=REPLACE_WITH_POOH_UUID) | *(link pending upload)* |
| **Eeyore** — flat, resigned, and completely correct about where to go | [Add to Waze](https://waze.com/ul?acvp=REPLACE_WITH_EEYORE_UUID) | *(link pending upload)* |
| **Tigger** — fast, bouncy, overconfident | [Add to Waze](https://waze.com/ul?acvp=REPLACE_WITH_TIGGER_UUID) | *(link pending upload)* |

Each works on any phone, in kilometres or miles. A pack lives on Waze's servers,
so a link keeps working for anyone forever once it exists.

Each is an original interpretation of a character as written in A. A. Milne's
books, generated from a licensed text-to-speech voice with written delivery
direction. **Never a clone of anyone's voice performance.** Full rights detail in
[docs/presets.md](docs/presets.md).

## One thing to know before you decide

**A custom Waze voice can never say a street name.** A pack is 43 fixed audio
files with no text-to-speech at drive time, so "turn left onto Bloor Street"
comes out as just "turn left".

That is a Waze constraint, not a limitation of this project, and it applies to
every custom voice anyone has ever made. Distances, turns, roundabout exits and
hazard warnings all work normally. If street names matter to you, stay on Waze's
built-in voice.

## Want to make one that does not exist yet?

That is what the SDK is for. Build a pack from **an API key and a character
idea**, or from **your own recordings**.

```powershell
winget install Gyan.FFmpeg
git clone https://github.com/ammar-adam/waze-voice-sdk
cd waze-voice-sdk
python scripts\wvs.py doctor
```

The fastest route is a text-to-speech key. No recording, no source media,
nothing to install beyond ffmpeg. Four providers are supported - `openai`,
`elevenlabs`, `hume` and `fish` - and they differ in kind, not just in price:
OpenAI and ElevenLabs pick a voice from a catalogue, Hume designs one from a
written description, and Fish plays whatever community model id you hand it.
[docs/tts.md](docs/tts.md) covers the trade-offs, including the rights ones.

```powershell
$env:OPENAI_API_KEY = "sk-..."
python scripts\wvs.py preflight                      # free: checks everything but the audio
python scripts\wvs.py quickstart --preset eeyore     # or --voice nova for the plain lines
```

That generates all 43 prompts, in both metric and imperial, normalized and packed
inside Waze's size budget. About a minute.

Building from **your own recordings** instead is the longer path, and what most of
this README describes:

```powershell
copy data\sources.sample.csv data\my-sources.csv
notepad data\my-sources.csv
python scripts\wvs.py run --sources data\my-sources.csv
```

To check the install without any of the above, `python tests\run_tests.py`
builds synthetic media and runs the whole pipeline over it.

## What this does, and what it does not

**It does:** produce a finished pack folder — 43 correctly-named MP3s, both unit
systems, loudness-matched, compressed to fit Waze's undocumented size cap, with a
checklist and a manifest.

**It does not upload.** Waze has no public API for this. Uploading is a separate,
manual step using a community tool, and pretending otherwise would waste your
time. [docs/upload-runbook.md](docs/upload-runbook.md) walks it start to finish;
it takes about a minute per pack and needs **no emulator**.

Once uploaded you get a permanent share link, which is what the table at the top
of this page is.

## The pipeline

```
your media  ->  extract  ->  clean  ->  synth  ->  normalize  ->  qa  ->  export  ->  upload
   + CSV        audio/       audio/     audio/      audio/               audio/       share link
                extracted    processed  synthesized master               export/pack
```

| Step | What it does |
| ---- | ------------ |
| `extract` | Cuts each clip from your source media with ffmpeg. Validates every CSV row before touching a file. |
| `clean` | Isolates the vocal. `ffmpeg` mode band-limits and denoises; `demucs` mode runs full source separation; `copy` passes through. |
| `synth` | Generates phrases your source never contained. A hosted API voice, or a clone of your own clips. Optional. |
| `normalize` | Measures each clip and applies one static gain so every prompt lands on the same loudness. |
| `qa` | Plays the pack back as a navigation route, chained the way Waze chains prompts. Records a pass/fail verdict per instruction. |
| `export` | Builds the uploadable pack: Waze filenames, both unit systems, bitrates allocated to fit the 0.8 MB budget. |

Run the lot with `wvs run`, or any step alone:

```powershell
python scripts\wvs.py extract --sources data\my-sources.csv
python scripts\wvs.py clean --mode demucs
python scripts\wvs.py normalize --force
python scripts\wvs.py qa --route chained_maneuvers
python scripts\wvs.py export
```

`wvs run` also takes `--from`, `--to`, and `--skip` so you can re-run part of it:

```powershell
python scripts\wvs.py run --from normalize --sources data\my-sources.csv
```

Every step is safe to re-run. Work that already has output is skipped unless you pass
`--force`.

[docs/pipeline.md](docs/pipeline.md) covers the design in detail.

## Describing your source clips

`data/sources.sample.csv` is the format. One row per take:

```csv
phrase_id,source_path,start,end,take,preferred,gain_db,notes
turn_left,C:\media\episode-one.m4a,00:12:03.100,00:12:04.250,1,,,first attempt
turn_left,C:\media\episode-one.m4a,00:41:55.000,00:41:56.100,2,1,,cleaner delivery
```

- Timestamps accept `HH:MM:SS.mmm`, `MM:SS.mmm`, or plain seconds. Use `duration`
  instead of `end` if you prefer.
- `take` lets you keep several attempts at one phrase. `preferred` picks which one ships;
  without it the lowest-numbered take wins.
- `gain_db` lifts a quiet delivery before normalization measures it.
- Video files work; the audio track is pulled out automatically.

Keep your real CSV and your media out of Git. Both are ignored by default.

## Choosing your phrases

[config/phrases.json](config/phrases.json) is the inventory: what the pack must contain,
what each file is called, and what to say. Edit it freely; no code changes needed.

It ships covering all 43 prompts Waze recognises, each carrying its Waze filename, unit
system, and a `weight` setting its share of the size budget. `wvs validate` checks pack
completeness against Waze's list, not just against itself.

## Tuning

[config/pipeline.json](config/pipeline.json) holds the audio targets, so extraction,
synthesis, normalization, and QA all agree without you repeating flags. Loudness target,
true-peak ceiling, silence trimming, denoise strength, QA timing, and the pack size budget
all live there.

Defaults: mono MP3, 44.1 kHz, 128 kbps, -16 LUFS integrated, -1.5 dBTP ceiling.
[docs/audio-targets.md](docs/audio-targets.md) explains why, including why short
navigation prompts need different loudness handling from ordinary program material.

## More than one voice

Each voice is a **pack**. Packs live side by side in one clone and share nothing:
separate source lists, separate clips, separate exports.

```powershell
python scripts\wvs.py pack new narrator --label "Narrator"
python scripts\wvs.py pack new sidekick --label "Sidekick"
python scripts\wvs.py pack list
```

Fill in each pack's `packs/<name>/sources.csv`, then build them independently:

```powershell
python scripts\wvs.py run --pack narrator
python scripts\wvs.py run --pack sidekick
python scripts\wvs.py qa  --pack sidekick
```

Every command takes `--pack`, or set `$env:WVS_PACK` once and leave it off.

A pack falls back to the shared `config/` for anything it does not override, so
the Waze prompt list is set up already. Give a pack its own copy only when it
needs different wording, `tts_text`, or budget weights:

```powershell
python scripts\wvs.py pack new sidekick --copy-phrases
```

Both packs produce the *same* Waze filenames, because Waze matches on filename.
They are separate packs, uploaded separately, and you switch between them on the
phone. One pack cannot hold two voices for the same prompt.

`packs/` is Git-ignored: it holds paths to your media and the audio built from it.

`WVS_AUDIO_ROOT` still takes precedence over everything, for redirecting the
audio tree without using packs at all.

## Repository layout

```text
waze_voice/          the library: every step is implemented here
  steps/             extract, clean, synth, normalize, qa, export, validate
  wazepack.py        Waze's filename list, unit systems, and size limit
  budget.py          per-clip bitrate allocation against the size budget
  media.py           every ffmpeg call in the project
  cli.py             the wvs command
scripts/             thin CLI wrappers, one per step, plus record_assist.py
tts/                 synthesis entry points: generate, prepare_dataset, train
config/              phrases.json, routes.sample.json, pipeline.json (shared)
presets/             character presets: voice, direction, and 43 lines
data/                source inventory CSV
packs/               one directory per voice, all Git-ignored
audio/               working directories, all Git-ignored
tests/               unittest suite, including an end-to-end ffmpeg run
docs/                setup, pipeline design, presets, upload runbook
```

## Legal boundary

Do not commit copyrighted media, extracted clips, synthesized character or celebrity
voices, trained model weights, demo videos, or finished packs containing audio you
cannot redistribute. The `.gitignore` is set up to make that the default outcome, but it
is not a substitute for judgement. Read [LEGAL.md](LEGAL.md).

## Contributing

The most useful thing you can contribute is **what happened when you put a pack on a
real phone**. Waze documents none of this; the filename list, the size limit, and the
share-link flow are all things people worked out and wrote down. Negative results count.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, house style, and what CI checks.
Security reports go through [SECURITY.md](SECURITY.md).

## Project status

Working and tested. The 43 filenames, the distance readings, and the size cap were all
verified against 11 real packs downloaded from Waze and transcribed offline; see
[docs/waze-import-spike.md](docs/waze-import-spike.md).

Still unconfirmed: no pack built by this tool has been uploaded and driven with yet, and
the exact distance at which each callout fires is not knowable from pack contents. If you
get there first, please [say so](../../issues/new?template=device-report.yml).

Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

The licence covers the tooling. It grants no rights to media you process, voices you
synthesize, or packs you produce. See [LEGAL.md](LEGAL.md).
