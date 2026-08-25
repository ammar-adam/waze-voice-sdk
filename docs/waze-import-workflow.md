# Getting a pack into Waze

## What is known, and what is not

**Known.** Waze has an in-app custom voice recorder at
`Settings > Voice and sound > Waze voice > Add a voice`. It records prompts through the
phone microphone. This is the only publicly documented route.

**Not known.** Whether a pre-rendered audio file can be injected directly, bypassing the
microphone. This SDK does not assume it can, and nothing it produces depends on it.

**Treat as unconfirmed.** Any ZIP or manifest import format for Waze custom voices. If you
find such a claim, reproduce it on your own device and app version before relying on it.
App behaviour changes between releases and differs between Android and iOS.

The honest position is that the recorder workflow definitely works and everything else is
a hypothesis you can test in about five minutes.

## Test it before you commit an hour

`audio/export/VERIFY-IMPORT-FIRST.md` is generated with every export and walks through
this. In short:

1. Note your exact Waze version from `Settings > About`. A result without a version number
   is not reproducible.
2. Record one prompt in the app, normally, in your own voice. Confirm it saves.
3. Try to reach the stored recording:
   - **Android:** look under `Android/media/com.waze/` with the system Files app. Content
     under `Android/media/` is readable without root; `Android/data/` generally is not on
     Android 11 and later. If you find it, try replacing it with the matching clip from
     `clips/`, keeping the original filename, format, and sample rate.
   - **iOS:** the app container is not user-accessible without a full backup round trip.
     Assume the recorder is the only path.
4. Start a route and confirm the prompt fires.

Three outcomes:

| Outcome | What it means | What to do |
| ------- | ------------- | ---------- |
| Direct replacement plays | A faster path exists on your device | Document it in [waze-import-spike.md](waze-import-spike.md) and open an issue. `pack-manifest.json` already carries the metadata an import script would need. |
| Only the recorder works | Expected | Work through `IMPORT_CHECKLIST.md`. |
| Something else | Menu moved, feature unavailable in your region, recorder behaves differently | Write down what you actually saw before adapting. |

## The recorder workflow

```powershell
python scripts\wvs.py export
python scripts\record_assist.py
```

`record_assist.py` walks the checklist one prompt at a time, shows the line to record,
plays the clip on a keypress, and saves progress after every prompt so an interrupted
session resumes with `--resume`. It beats juggling a file browser while holding a phone.

Waze asks for prompts in its own fixed order, which may not match the pack's numbering.
Match by wording, not by number.

### Getting a good microphone pass

If the recorder is your route, the quality of this pass now dominates everything the
pipeline did upstream. Worth getting right:

- Quiet room. The recorder captures whatever else is happening.
- Phone 15-30 cm from the speaker. Closer distorts; further picks up the room.
- Set playback volume so the loudest prompt does not distort, then **do not touch it
  again**. Changing volume mid-session undoes the loudness normalization the pipeline
  just did.
- Record one prompt, play it back inside Waze, and check it before doing the other
  seventeen.
- Exported clips carry about 60 ms of lead-in silence so the recorder does not clip the
  first syllable. Start playback promptly once recording begins.

## If the prompt list is wrong

`config/phrases.json` is deliberately conservative and was written before the current Waze
prompt list was confirmed on a device. If the app asks for prompts that are not in it, or
skips ones that are, edit the file. It needs no code changes.

Please also record what the app actually asked for in
[waze-import-spike.md](waze-import-spike.md).

## Reporting back

This document gets shorter and more definite as people write down what they saw. Device,
OS version, Waze version, date, steps, result. Negative results are useful: "the
`Android/media/com.waze/` directory does not exist on Waze 5.x" is worth knowing.
