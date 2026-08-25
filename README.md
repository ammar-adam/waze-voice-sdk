# Waze Voice SDK

Windows-first toolkit for turning audio you own into a custom navigation voice pack.

Point it at your media files and a CSV of timestamps. It cuts the clips, isolates the
vocal, synthesizes any lines your source material never said, matches every clip to one
consistent loudness, lets you audition the result as a driving route, and exports an
ordered folder with the paperwork you need to get it into Waze.

This repository ships **no audio, no model weights, and no voice packs**. It is a
production pipeline. What you feed it, and whether you have the right to use it, is
yours to decide. See [LEGAL.md](LEGAL.md).

Not affiliated with Waze, Google, or any rights holder.

## The import question, up front

Waze's in-app custom voice recorder is the only publicly documented way to get a custom
voice onto a device. Whether a **pre-rendered clip can be injected directly**, skipping
the microphone, is **not verified**, and this SDK does not pretend otherwise.

So the export step produces three things: clips ordered for the recorder workflow that
definitely works, a machine-readable manifest that a direct-import path could consume if
one turns out to exist, and `VERIFY-IMPORT-FIRST.md`, a five-minute check that tells you
which situation you are actually in before you spend an hour recording prompts by hand.

If you establish something concrete on real hardware, write it into
[docs/waze-import-spike.md](docs/waze-import-spike.md).

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
| [requirements-tts.txt](requirements-tts.txt) | Coqui TTS synthesis | See [docs/tts.md](docs/tts.md) - **needs Python 3.9-3.11** |

## Quick start

```powershell
python tests\run_tests.py
```

That builds synthetic media, runs the whole pipeline on it, and checks the audio that
comes out. It needs no media of your own, so it is the fastest way to confirm your
install works.

Then, for real:

```powershell
copy data\sources.sample.csv data\my-sources.csv
notepad data\my-sources.csv
python scripts\wvs.py run --sources data\my-sources.csv
```

## The pipeline

```
your media  ->  extract  ->  clean  ->  synth  ->  normalize  ->  qa  ->  export
   + CSV        audio/       audio/     audio/      audio/               audio/
                extracted    processed  synthesized master               export
```

| Step | What it does |
| ---- | ------------ |
| `extract` | Cuts each clip from your source media with ffmpeg. Validates every CSV row before touching a file. |
| `clean` | Isolates the vocal. `ffmpeg` mode band-limits and denoises; `demucs` mode runs full source separation; `copy` passes through. |
| `synth` | Generates phrases your source never contained, in the voice of your own cleaned clips. |
| `normalize` | Measures each clip and applies one static gain so every prompt lands on the same loudness. |
| `qa` | Plays the pack back as a navigation route, chained the way Waze chains prompts. Records a pass/fail verdict per instruction. |
| `export` | Ordered clips, a recording checklist, a pack manifest, and the import verification guide. |

Run the lot with `wvs run`, or any step alone:

```powershell
python scripts\wvs.py extract --sources data\my-sources.csv
python scripts\wvs.py clean --mode demucs
python scripts\wvs.py normalize --force
python scripts\wvs.py qa --route highway_merge
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

The shipped list is deliberately conservative. Confirm the current Waze prompt list on a
real device before treating it as complete.

## Tuning

[config/pipeline.json](config/pipeline.json) holds the audio targets, so extraction,
synthesis, normalization, and QA all agree without you repeating flags. Loudness target,
true-peak ceiling, silence trimming, denoise strength, and QA timing all live there.

Defaults: mono MP3, 44.1 kHz, 128 kbps, -16 LUFS integrated, -1.5 dBTP ceiling.
[docs/audio-targets.md](docs/audio-targets.md) explains why, including why short
navigation prompts need different loudness handling from ordinary program material.

## Building more than one pack

Set `WVS_AUDIO_ROOT` to keep separate working trees from one clone:

```powershell
$env:WVS_AUDIO_ROOT = "D:\voices\narrator"
python scripts\wvs.py run --sources data\narrator.csv
```

## Repository layout

```text
waze_voice/          the library: every step is implemented here
  steps/             extract, clean, synth, normalize, qa, export, validate
  media.py           every ffmpeg call in the project
  cli.py             the wvs command
scripts/             thin CLI wrappers, one per step, plus record_assist.py
tts/                 synthesis entry points: generate, prepare_dataset, train
config/              phrases.json, routes.sample.json, pipeline.json
data/                source inventory CSV
audio/               working directories, all Git-ignored
tests/               unittest suite, including an end-to-end ffmpeg run
docs/                setup, pipeline design, audio targets, TTS, Waze import
```

## Legal boundary

Do not commit copyrighted media, extracted clips, synthesized character or celebrity
voices, trained model weights, demo videos, or finished packs containing audio you
cannot redistribute. The `.gitignore` is set up to make that the default outcome, but it
is not a substitute for judgement. Read [LEGAL.md](LEGAL.md).

## License

MIT. See [LICENSE](LICENSE).
