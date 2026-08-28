# Upload runbook

Getting three finished packs onto Waze, on Windows, start to finish.

## Read this first: no emulator is involved

If you have seen the BlueStacks-and-root walkthrough, **that method is
deprecated** and you do not need any of it. No emulator, no rooting, no file
explorer, no reserving slots with junk recordings, no keeping an edit screen
open, no hunting for `custom_prompts_temp`.

The current method is a Python script that authenticates to Waze as an anonymous
client, uploads a tarball of your MP3s, and prints a share link. It runs on your
own machine in about a minute per pack.

Everything in the community discussion about BlueStacks failing to root, MEmu
working instead, and LDPlayer not working at all is people struggling with the
old method. Skip it.

**What this SDK does and does not do.** It produces a valid pack folder. It does
**not** upload. The upload is a separate tool, run manually, and this runbook is
the manual part.

---

## Step 0: build the packs

```powershell
python scripts\wvs.py preflight
python scripts\build_all.py
```

`build_all` builds every character you hold a provider key for, checks each
against the budget, and copies it into the uploader's `input_packs` under the
name Waze will show the driver. Anything missing a key is reported as skipped.

To do it by hand instead, one preset at a time:

```powershell
python scripts\wvs.py quickstart --preset pooh --accept-voice-terms
```

Each run overwrites `audio/export/`, so copy each pack out before building the
next, or use a pack per voice:

```powershell
python scripts\wvs.py pack new pooh --label "Winnie the Pooh"
python scripts\wvs.py quickstart --pack pooh --preset pooh --accept-voice-terms
```

That leaves the finished files at `packs/pooh/audio/export/pack/`.

`--accept-voice-terms` is required once per clone. Without it the first synth
run exits instead of building.

Check the utilisation line on each build. Target is 85% of Waze's cap; anything
above 92% fails the build. Ours estimate at 82%.

**Why that matters here specifically:** the upload tool re-compresses any pack
over 0.795 MB, using one flat bitrate for every file (binary-searched
between 16 and 128 kbps). That would throw away this
SDK's per-clip allocation and hand the drive-start greeting the same bitrate as
"turn left". Staying under the cap means the uploader passes your files through
untouched.

---

## Step 1: install the upload tool

```powershell
git clone https://github.com/pipeeeeees/waze-voicepack-links
cd waze-voicepack-links
```

**Use Python 3.12.** The project's own README says the maintainer has problems on
3.13, and its `requirements.txt` pins `protobuf==3.10.0`, which will not build on
3.13. This is the single most likely thing to cost you an hour.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt` lists `openai-whisper`, which pulls in torch: roughly 2 GB
for a language-detection helper the upload path never imports. Verified against
the source. To skip it:

```powershell
findstr /v openai-whisper requirements.txt > req-upload.txt
python -m pip install -r req-upload.txt
```

If you do not have 3.12:

```powershell
winget install Python.Python.3.12
```

ffmpeg must be on `PATH`. You already have it if this SDK works.

---

## Step 2: stage the packs

Each pack is one folder under **`mp3_upload\input_packs\`** (not the repository
root), **and the folder name becomes the voice name shown in Waze**: it is sent
as `set_name` and as the display label. Choose it deliberately.

```powershell
mkdir "mp3_upload\input_packs\Winnie the Pooh"
copy C:\Users\aaamm\waze-voice-sdk\packs\pooh\audio\export\pack\*.mp3 "mp3_upload\input_packs\Winnie the Pooh\"
```

Repeat for the other two. You can stage all three and upload them in one run.

Sanity check before you continue: each folder should hold exactly 43 `.mp3`
files.

```powershell
(Get-ChildItem "mp3_upload\input_packs\Winnie the Pooh\*.mp3").Count
```

**Ingestion accepts a pack containing as little as one recognised file.**
Missing files print a warning and the upload proceeds anyway. Do not treat
reaching the upload stage as evidence the pack is complete; that is what step 4
is for.

**Clear `mp3_upload\compressed_packs\` between runs.** The upload stage iterates
over every folder it finds there, not over what you just staged, so a pack left
from an earlier run is silently uploaded again under a fresh UUID.

---

## Step 3: upload

Run from the **repository root**, not from inside `mp3_upload/`. Ingestion and
compression resolve their paths from the script's own location and work from
anywhere, but the upload stage hardcodes the relative path
`./mp3_upload/compressed_packs/`, so running from anywhere else gets through
both earlier phases and then fails with a confusing missing-directory error.

```powershell
python mp3_upload\main.py
```

It runs three phases and prints progress for each:

1. **Ingestion.** Validates filenames against its own list and checks each file
   decodes. Files it does not recognise are ignored silently; missing files are a
   warning, not an error.
2. **Compression.** Only runs if the pack exceeds 0.795 MB. Ours should not trigger
   it. If it does, your pack was bigger than the build reported and something is
   wrong upstream.
3. **Upload.** Prints, per pack:

```
✅ Upload of Winnie the Pooh successful.
https://waze.com/ul?acvp=<UUID>
https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz
```

**Save both URLs for each pack immediately.** The UUID is the only handle on the
pack and nothing else can recover it.

---

## Step 4: verify, before you trust it

"Upload successful" means the server accepted the request. It does not mean the
pack is right. Prove it:

```powershell
cd C:\Users\aaamm\waze-voice-sdk
python scripts\wvs.py verify-upload <UUID> --pack-dir packs\pooh\audio\export\pack
```

This downloads the live pack from Waze, unpacks it, and checks:

- all 43 files present, none that Waze would ignore
- no core prompt missing
- no silent clips (expected only for `TickerPoints`)
- every file byte-identical in size to what you built

A byte-size mismatch means what is live is not what you built. That is the check
that catches a placeholder surviving, or an older revision being served.

---

## Step 5: put it on the phone

Open `https://waze.com/ul?acvp=<UUID>` on the phone, with Waze installed. It
offers to add the voice. Then `Settings > Voice and sound` and select it.

Drive or simulate a route and listen for:

- a distance callout chained onto a maneuver, which exercises the two file sets
  most likely to be wrong
- **the unit system your phone is actually set to.** On kilometres you should
  hear "In two hundred meters"; on miles, "In point one miles". Our packs ship
  both, so both should work.

---

## Failure modes

| What you see | What it means | Fix |
| --- | --- | --- |
| **Share button greys out right after saving** | Server-side rejection, almost always oversize. The classic signal. | Get the pack under 0.795 MB. `wvs export` reports utilisation; target 85%. |
| **Link works, every prompt is silence** | The upload landed but the audio did not, or placeholders were uploaded. | `wvs verify-upload` will show silent clips. Rebuild and re-upload. |
| **Only distance prompts are silent** | Reported by a user in Jan 2026 who recorded only metric distances. The other unit set was left empty, so a phone on the other system hears nothing. | Ship `units: both`, which every shipped preset does. |
| `The MP3 directory does not exist.` | Ran the script from the wrong directory. | Run `python mp3_upload\main.py` from the repository root. |
| `UnicodeEncodeError: 'charmap' codec can't encode character '📝'` | The uploader prints emoji. Windows encodes console output as cp1252 whenever stdout is not a real console: piped, redirected to a file, or run from an IDE. Reproduced here. | `$env:PYTHONIOENCODING = "utf-8"` before running, or do not redirect the output. |
| `pip install` fails building protobuf | Python 3.13. | Use 3.12. |
| Upload prints a link, download 404s | The upload did not actually land despite the message. | Re-run. If it repeats, the pack is likely being rejected for size. |
| Waze does not offer to add the voice | Link opened without Waze installed, or opened on desktop. | Open on the phone with Waze installed. |

---

## What I could not verify

- **No upload has been performed from here.** The install, the venv on 3.12,
  and the filename allowlist are verified locally: our 43 filenames match the
  uploader's `valid_waze_filenames.txt` exactly, set for set. Phases 1 and 2 are
  read from its source and **rehearsed end to end** with synthetic audio: a
  43-file Pooh pack was built, ingested, and reported `Already within limit
  (0.64 MB)`, so compression never fired and the per-clip bitrate allocation
  reached the upload stage intact. The network call in phase 3 is the only part
  nobody here has run.
- **The auth flow may be fragile.** It impersonates a Waze client with a
  hand-built protobuf payload and a hardcoded app version (`4.106.0.1`). That is
  exactly the kind of thing that breaks when Waze ships an update, and nothing in
  this SDK can detect it in advance. If the login POST fails, that is what
  happened, and the fix is upstream.
- **Trigger distances remain unconfirmed.** Which callout fires at which distance
  is still not known from pack contents alone. If you note it while driving,
  `docs/waze-import-spike.md` has a place for it.

## Two things worth knowing before you publish

**The UUID is the whole security model.** Anyone holding it can download every
MP3 in your pack, with no authentication. Keep it off camera if you film this.

**Trademark is untouched by any of this.** The Milne text is public domain in the
US and Canada; the character *names* are live trademarks. Publishing packs under
those names is a decision to make deliberately, and none of the engineering here
changes it.
