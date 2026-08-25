# Windows setup

## Base install

Windows 10 or newer, Python 3.10+, and ffmpeg. Nothing else for the core pipeline.

```powershell
winget install Python.Python.3.11
winget install Gyan.FFmpeg
```

**Open a new terminal after installing ffmpeg** so `PATH` picks it up. This is the single
most common setup problem.

```powershell
git clone https://github.com/ammar-adam/waze-voice-sdk
cd waze-voice-sdk
python scripts\wvs.py doctor
```

`doctor` lists what is present, what is missing, and which step each missing piece blocks.

Confirm the whole thing actually works, with no media of your own:

```powershell
python tests\run_tests.py
```

That builds synthetic audio with ffmpeg, runs the real pipeline over it, and checks the
output.

## Optional: Demucs

Needed only for `clean --mode demucs`. Pulls in PyTorch, several GB.

```powershell
python -m pip install -r requirements-clean.txt
```

For a CUDA build, install torch from the selector at
<https://pytorch.org/get-started/locally/> first, then Demucs.

The default `--mode ffmpeg` needs none of this and handles room tone and hiss well enough
for most dialogue. Reach for Demucs when a line is buried under music.

## Optional: voice synthesis

Needed only for the synthesis step, which fills phrases your source media never said.

```powershell
python -m pip install -r requirements-tts.txt
```

That installs Chatterbox, which runs on the same interpreter as the rest of the pipeline
(Python 3.10 to 3.13). No separate virtual environment needed. It pulls in PyTorch, so
expect a multi-GB download; CPU is fine for a voice pack, which is a handful of
one-second clips.

Skip it entirely if you would rather record the missing lines yourself. The pipeline
carries on without it and lists those phrases in the export checklist. Full walkthrough in
[tts.md](tts.md).

## PowerShell notes

- If scripts are blocked when activating a venv:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

- Paths with spaces need quoting in the source CSV. The parser strips surrounding double
  quotes.
- Backslash paths are fine throughout. So are forward slashes.
- Console output is deliberately ASCII-only, so a legacy code page will not mangle it.

## Where things go

```text
audio/raw/            optional staging for your source media
audio/extracted/      cut clips, phrase__take1.wav
audio/processed/      cleaned clips
audio/synthesized/    generated clips
audio/master/         final normalized MP3s
audio/export/         the pack, ready for import
audio/.work/          scratch renders, safe to delete
audio/build-manifest.json   what happened to each phrase
audio/qa-report.json        pass/fail verdicts from QA
```

All of it is Git-ignored.

To keep separate working trees from one clone, set `WVS_AUDIO_ROOT`:

```powershell
$env:WVS_AUDIO_ROOT = "D:\voices\narrator"
```

## Troubleshooting

**`ffmpeg was not found on PATH`** — installed, but the terminal predates the install.
Open a new one.

**`Source media file(s) not found`** — the paths in your CSV are wrong or the drive is not
mounted. Every missing path is listed at once, before any work starts.

**A clip measures as silence** — the timestamps point at a gap, or cleaning removed the
signal. Play the file in `audio/extracted/` to see which. If cleaning is the culprit the
step reports a revert, and lowering `clean.denoise_floor_db` will help.

**A clip is flagged as a loudness outlier** — the source had heavy background noise or was
already clipping. Try `--mode demucs`, or cut a different take.

**Demucs produced no vocal stem** — usually the clip is too short. Extend the timestamps
by a few hundred milliseconds and re-extract with `--force`.

**Everything is stale after a config change** — steps skip work that already has output.
Add `--force`.
