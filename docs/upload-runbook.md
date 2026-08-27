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
python scripts\wvs.py quickstart --preset eeyore
python scripts\wvs.py quickstart --preset pooh
python scripts\wvs.py quickstart --preset tigger
```

Each run overwrites `audio/export/`, so copy each pack out before building the
next, or use a pack per voice:

```powershell
python scripts\wvs.py pack new eeyore  --label "Eeyore"
python scripts\wvs.py quickstart --pack eeyore --preset eeyore
```

That leaves the finished files at `packs/eeyore/audio/export/pack/`.

Check the utilisation line on each build. Target is 85% of Waze's cap; anything
above 92% fails the build. Ours estimate at 82%.

**Why that matters here specifically:** the upload tool re-compresses any pack
over 0.8 MB, using one flat bitrate for every file. That would throw away this
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

If you do not have 3.12:

```powershell
winget install Python.Python.3.12
```

ffmpeg must be on `PATH`. You already have it if this SDK works.

---

## Step 2: stage the packs

Each pack is one folder under `input_packs/`, **and the folder name becomes the
voice name shown in Waze**. Choose it deliberately.

```powershell
mkdir input_packs\Eeyore
copy C:\Users\aaamm\waze-voice-sdk\packs\eeyore\audio\export\pack\*.mp3 input_packs\Eeyore\
```

Repeat for the other two. You can stage all three and upload them in one run.

Sanity check before you continue: each folder should hold exactly 43 `.mp3`
files.

```powershell
(Get-ChildItem input_packs\Eeyore\*.mp3).Count
```

---

## Step 3: upload

Run from the **repository root**, not from inside `mp3_upload/`. The uploader
resolves `./mp3_upload/compressed_packs/` relative to the working directory, so
running it from the wrong place fails with a confusing missing-directory error.

```powershell
python mp3_upload\main.py
```

It runs three phases and prints progress for each:

1. **Ingestion.** Validates filenames against its own list and checks each file
   decodes. Files it does not recognise are ignored silently; missing files are a
   warning, not an error.
2. **Compression.** Only runs if the pack exceeds 0.8 MB. Ours should not trigger
   it. If it does, your pack was bigger than the build reported and something is
   wrong upstream.
3. **Upload.** Prints, per pack:

```
✅ Upload of Eeyore successful.
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
python scripts\wvs.py verify-upload <UUID> --pack-dir packs\eeyore\audio\export\pack
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
| **Share button greys out right after saving** | Server-side rejection, almost always oversize. The classic signal. | Get the pack under 0.8 MB. `wvs export` reports utilisation; target 85%. |
| **Link works, every prompt is silence** | The upload landed but the audio did not, or placeholders were uploaded. | `wvs verify-upload` will show silent clips. Rebuild and re-upload. |
| **Only distance prompts are silent** | Reported by a user in Jan 2026 who recorded only metric distances. The other unit set was left empty, so a phone on the other system hears nothing. | Ship `units: both`, which all three presets do. |
| `The MP3 directory does not exist.` | Ran the script from the wrong directory. | Run `python mp3_upload\main.py` from the repository root. |
| `pip install` fails building protobuf | Python 3.13. | Use 3.12. |
| Upload prints a link, download 404s | The upload did not actually land despite the message. | Re-run. If it repeats, the pack is likely being rejected for size. |
| Waze does not offer to add the voice | Link opened without Waze installed, or opened on desktop. | Open on the phone with Waze installed. |

---

## What I could not verify

- **No upload has been performed from here.** Everything above is read from the
  uploader's source and its README. The mechanism is clear, but the first real
  run is yours.
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
