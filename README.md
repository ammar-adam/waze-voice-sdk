# Waze Voice SDK

[![CI](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Windows-first toolkit for turning audio you own into a custom navigation voice pack.

Point it at your media files and a CSV of timestamps. It cuts the clips, isolates the
vocal, synthesizes any lines your source material never said, matches every clip to one
consistent loudness, lets you audition the result as a driving route, and exports an
ordered folder with the paperwork you need to get it into Waze.

This repository ships **no audio, no model weights, and no voice packs**. It is a
production pipeline. What you feed it, and whether you have the right to use it, is
yours to decide. See [LEGAL.md](LEGAL.md).

Not affiliated with Waze, Google, or any rights holder.

## How packs get onto a phone

Waze stores custom voice packs **on its servers**, not on the device, and hands out share
links of the form `https://waze.com/ul?acvp=<UUID>`. So the creation device and the
consumption device are decoupled: build the pack on a PC, upload it, open the link on your
phone. The Waze app itself is record-only, and that does not matter.

Two things decide whether a pack works, and both fail silently:

- **Exact filenames.** Waze matches on filename and ignores anything else without an
  error. `200.mp3` is the 0.1 mile callout; `1500.mp3` is one mile; `uturn.mp3` is
  lowercase. Metric and imperial distances are two separate file sets and a pack needs
  both.
- **An aggregate size limit of roughly 0.8 MB** across every MP3. Exceeding it is
  rejected server-side, showing up as a share button that greys out or a pack that plays
  silence.

The export step handles both: correct names, both unit systems, and per-clip bitrate
allocation to fit the budget. It prints the finished size against the limit before you
upload.

Upload itself is done with the community tooling at
[waze-voicepack-links](https://github.com/pipeeeeees/waze-voicepack-links), which is also
the source for the filename list and the size limit. Full detail in
[docs/waze-import-workflow.md](docs/waze-import-workflow.md).

## Install

Requirements: Windows 10 or newer, Python 3.10+, and ffmpeg.

```powershell
winget install Gyan.FFmpeg
```

Open a new terminal so `PATH` picks it up, then:

```powershell
git clone https://github.com/ammar-adam/waze-voice-sdk
cd waze-voice-sdk
python scripts/wvs.py doctor
```

`doctor` reports what is present, what is missing, and which step each missing piece
blocks. The core pipeline needs no Python packages at all: everything runs on the
standard library plus ffmpeg.

Two optional extras, each isolated so nobody downloads PyTorch to cut a clip:

| Extra | Enables | Install |
| ----- | ------- | ------- |
| [requirements-clean.txt](requirements-clean.txt) | Demucs vocal separation | `python -m pip install -r requirements-clean.txt` |
| [requirements-tts.txt](requirements-tts.txt) | Chatterbox voice synthesis, offline | `python -m pip install -r requirements-tts.txt` |
| *(none needed)* | ElevenLabs / OpenAI synthesis | just an API key, see [docs/tts.md](docs/tts.md) |

## Quick start

Pick a character, get a pack. One command, no configuration:

```powershell
$env:OPENAI_API_KEY = "sk-..."
python scripts\wvs.py presets list
python scripts\wvs.py preflight              # free: checks everything but the audio
python scripts\wvs.py quickstart --preset eeyore
```

A **preset** is a voice, a delivery direction, and all 43 Waze prompts rewritten
in that character's register. Three ship: `eeyore`, `pooh`, and `tigger`, each an
original interpretation of a public-domain book character, generated from a
licensed voice and never a clone of any performance. See
[docs/presets.md](docs/presets.md).

Or pick any voice and use the standard lines:

```powershell
$env:OPENAI_API_KEY = "sk-..."
python scripts\wvs.py voices
python scripts\wvs.py quickstart --voice nova
```

That generates all 43 prompts Waze recognises, in both metric and imperial,
normalized and packed inside Waze's size budget. About a minute, and roughly a
thousand characters of TTS.

`elevenlabs` works the same way and has a much larger voice library:

```powershell
$env:ELEVENLABS_API_KEY = "..."
python scripts\wvs.py voices --provider elevenlabs --search narrator
python scripts\wvs.py quickstart --provider elevenlabs --voice <id>
```

Building from **your own recordings** instead is the longer path, and the one
the rest of this README describes:

```powershell
copy data\sources.sample.csv data\my-sources.csv
notepad data\my-sources.csv
python scripts\wvs.py run --sources data\my-sources.csv
```

To check the install without any of the above, `python tests\run_tests.py`
builds synthetic media and runs the whole pipeline over it.

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
docs/                setup, pipeline design, audio targets, TTS, Waze import
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

Working and tested, with one honest gap: nobody has yet confirmed a pack built by this
tool on a real device end to end. Everything up to the upload is verified, including
against real ffmpeg and real Demucs. If you get there first, please
[say so](../../issues/new?template=device-report.yml).

Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

The licence covers the tooling. It grants no rights to media you process, voices you
synthesize, or packs you produce. See [LEGAL.md](LEGAL.md).
