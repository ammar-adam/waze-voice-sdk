# Waze Voice SDK

[![CI](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/ammar-adam/waze-voice-sdk/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Character voices for Waze navigation.

## Just want the voices?

**[Pick one here](https://claude.ai/code/artifact/02f68bd0-af45-409b-a48a-448810b0f430)** — tap to hear it, tap to install. Nothing to set up,
no account. Open it on a phone with Waze installed, because the install link
only does anything on a device running the app.

The direct links, if you would rather skip the page:

| Voice | | Rights |
| ----- | - | ------ |
| **Bugs Bunny** — unbothered, wisecracking, a beat ahead of you | [Add to Waze](https://waze.com/ul?acvp=d1bbee51-c541-478f-a3a2-0ae9e319a6fd) | in copyright |
| **Winnie the Pooh** — warm, unhurried, audibly thinking it through | [Add to Waze](https://waze.com/ul?acvp=e6ad4e53-06dd-44ff-bbd1-c8a5cd6fb6b8) | text PD |
| **Tigger** — fast, bouncy, overconfident | [Add to Waze](https://waze.com/ul?acvp=9046b9ab-c7b0-459c-b035-4b51b4d31d42) | text PD |
| **Paddington** — unfailingly polite, marmalade under the hat | [Add to Waze](https://waze.com/ul?acvp=8d800927-198d-4826-aa22-4c7ad60d1adc) | in copyright |
| **Cookie Monster** — blunt, delighted, entirely present tense | [Add to Waze](https://waze.com/ul?acvp=2f6ccacd-9d5c-415b-a580-54b17c511653) | in copyright |
| **Elmo** — bright, giggly, third person throughout | [Add to Waze](https://waze.com/ul?acvp=bd90b917-c393-4880-9ff4-9637fe3117c8) | in copyright |
| **Daffy Duck** — loud, theatrical, personally offended by traffic | [Add to Waze](https://waze.com/ul?acvp=befcdaf8-2409-4302-b2d3-f5c4c6dca9cf) | in copyright |

Each was verified after upload: downloaded back from Waze, all 43 files
present, none silent, none misnamed, every file byte-identical to the build.
`wvs verify-upload <uuid>` does that for any pack, including somebody else's.

An eighth preset, `eeyore`, ships without a published pack. Build it with
`python scripts\wvs.py quickstart --preset eeyore`.

**The rights column is not decoration.** Pooh and Tigger rest on A. A. Milne's
1926 and 1928 books, whose copyright has expired in the US and Canada, and
their scripts are original writing in that register. The other five are
characters still in copyright, spoken by community voice models that clone the
original performances. No permission from any rights holder or performer is
claimed. `rights.status` is a required preset field with no default, so a
preset cannot decline to answer; [docs/presets.md](docs/presets.md) sets out
what each one covers.

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
$env:OPENAI_API_KEY = "<paste your real key here>"
python scripts\wvs.py doctor                         # confirms the key looks real
python scripts\wvs.py preflight                      # free: checks everything but the audio
python scripts\wvs.py quickstart --preset eeyore --accept-voice-terms
```

`--accept-voice-terms` is asked once per clone and recorded locally; without it
the first build stops rather than generating anything. `doctor` is worth the two
seconds: setting the variable to a placeholder satisfies every emptiness check
in the pipeline and then fails as a 401 partway through a build, so it is
checked for explicitly.

That generates all 43 prompts, in both metric and imperial, normalized and packed
inside Waze's size budget. About a minute.

To build every character you have a key for and stage each one for upload:

```powershell
python scripts\build_all.py
```

Characters whose provider key is missing are reported as skipped rather than
failing the run, so it is safe before you have finished signing up for anything.

Building from **your own recordings** instead is the longer path, and what most of
this README describes:

```powershell
copy data\sources.sample.csv data\my-sources.csv
notepad data\my-sources.csv
python scripts\wvs.py run --sources data\my-sources.csv
```

Every command is also available as `wvs` if you install the package:

```powershell
python -m pip install -e .
wvs preflight
```

The scripts path needs no install at all, which is why the docs use it.

To check the install without any of the above, `python tests\run_tests.py`
builds synthetic media and runs the whole pipeline over it.

## Where the rest of the documentation is

| | |
| --- | --- |
| [docs/tts.md](docs/tts.md) | The four providers, what each is good at, and the rights questions each raises |
| [docs/presets.md](docs/presets.md) | How a character is defined, and how to add one |
| [docs/pipeline.md](docs/pipeline.md) | What each step does to the audio, and why |
| [docs/upload-runbook.md](docs/upload-runbook.md) | Getting a finished pack onto Waze, start to finish |
| [docs/windows-setup.md](docs/windows-setup.md) | ffmpeg, Python, and the Windows-specific traps |
| [docs/audio-targets.md](docs/audio-targets.md) | Loudness and size targets, and where the numbers came from |
| [docs/waze-import-workflow.md](docs/waze-import-workflow.md) | How Waze packs actually work |
| [docs/waze-import-spike.md](docs/waze-import-spike.md) | What was measured from real packs, and what is still unverified |

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

## What had to be worked out

Waze has no API for custom voices and publishes nothing about the format. All
of this came from pulling apart real packs.

**A pack is exactly 43 MP3s with fixed names.** A file Waze does not recognise
is ignored silently — not rejected, not warned about, just absent at the
junction. `wazepack.py` holds the list and `wvs preflight` checks a build
against it before you spend anything.

**The distance filenames do not mean what they look like.** `1500.mp3` is "in
one mile", not 1.5 km; `1500meters.mp3` is the metric one. Confirmed twice, by
different routes: eleven real packs downloaded and transcribed offline with
Vosk ([docs/waze-import-spike.md](docs/waze-import-spike.md)), and later by a
community bug report where three of these slots had been rotated in a shipped
pack and nobody noticed until somebody drove it.

**Metric and imperial are separate file sets in the same pack.** Ship one and
drivers on the other system hear Waze's own voice for distances, mid-drive.
Presets default to `units: both`.

**Waze replays the maneuver clip at every distance callout.** Approaching one
turn you hear it three or four times — 800 m, 400 m, 200 m, junction — while
the distance clip changes each time. That inverts where character can go: a
catchphrase on `turn_left` is a catchphrase four times a minute, and the same
line spread across the nine distance files is heard once each. Tests enforce
the split.

**There is an undocumented size cap around 0.8 MB**, and exceeding it fails
silently. The exporter allocates bitrate per clip against a byte budget rather
than encoding everything at one rate, so frequent short prompts stay clean and
long rare ones absorb the loss. `wvs export` reports utilisation; the build
fails above 92%.

**Nothing downstream can tell you the audio is stale.** A pack rebuilt from an
edited script but serving yesterday's clips is real audio, correctly named, the
right length, and byte-identical to a local build that is equally stale — so
every check agrees with itself. Staging now refuses a pack whose preset is
newer than its audio.

## Project status

Working, and in use. Seven packs built by this tool are live on Waze, verified
byte-identical after upload, and driven with.

**Trigger distances are confirmed correct** — which callout fires at which
range was the last thing not knowable from pack contents, and a real drive
settled it.

Still worth reporting if you hit it: the community uploader can drop a pack
from a batch silently, succeeding on retry with no change. Count its success
lines. If you find something else,
[say so](../../issues/new?template=device-report.yml).

Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

The licence covers the tooling. It grants no rights to media you process, voices you
synthesize, or packs you produce. See [LEGAL.md](LEGAL.md).
