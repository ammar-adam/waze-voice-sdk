# Audio targets

Why the defaults in `config/pipeline.json` are what they are.

## Format

| Setting | Default | Reason |
| ------- | ------- | ------ |
| Container | MP3, 128 kbps | Universally decodable. A navigation prompt is a second of speech; the format is not the limiting factor. |
| Channels | Mono | Prompts play through a phone speaker or one car channel. Stereo doubles the size for nothing. |
| Sample rate | 44.1 kHz | Matches Demucs' native rate, so the separation stage involves no resampling round trip. |

Everything upstream of `audio/master/` stays 16-bit PCM WAV. Lossy encoding happens once,
at the end, rather than compounding through each stage.

## Loudness

| Setting | Default |
| ------- | ------- |
| Integrated loudness | -16 LUFS |
| True peak ceiling | -1.5 dBTP |
| Tolerance | 1.5 LU |

-16 LUFS is the common target for mono speech intended for mobile playback. It sits above
broadcast television levels, which matters because a prompt competes with road noise, and
below the point where a phone speaker starts distorting.

The -1.5 dBTP ceiling leaves headroom for the intersample peaks that lossy encoding
introduces. A file that peaks at exactly 0 dBFS before encoding can exceed it afterwards
and clip on playback.

Anything landing further than the tolerance from target after normalization is reported
as an outlier. In practice that means the source clip had a problem: heavy background
noise raising the measured loudness, or clipping already present in the original.

## Short clips

Navigation prompts are routinely under two seconds, and that breaks the normal way of
measuring loudness.

EBU R128 integrated loudness is computed over 400 ms blocks with a 100 ms hop, and gated:
blocks below -70 LUFS absolute, and blocks more than 10 LU below the ungated mean, are
discarded. ffmpeg warns that inputs shorter than about three seconds cannot be measured
accurately, and `loudnorm` falls back to dynamic mode on them, which compresses.

The fix used here is to **pad the clip with digital silence before measuring**. The gating
discards silent blocks, so padding does not change the reported loudness of the speech. It
only gives the measurement window enough material to run on. The gain derived from that
measurement is then applied to the unpadded clip.

This is checked rather than assumed. Measuring a five-second tone with and without six
seconds of appended silence gives results 0.13 LU apart, well inside the tolerance.
`waze_voice/media.py:measure_loudness` carries the same note; `short_clip_seconds` sets
the threshold.

## Silence and padding

| Setting | Default | Reason |
| ------- | ------- | ------ |
| `trim.threshold_db` | -45 dB | Below typical room tone, above the noise floor of a clean recording. |
| `trim.lead_in_ms` | 60 ms | Recorders and playback chains routinely swallow the first few milliseconds. Better a hair of silence than a clipped consonant. |
| `trim.lead_out_ms` | 120 ms | Prevents the tail being cut when the next prompt is queued. |
| `trim.fade_ms` | 15 ms | Silence trimming can land mid-waveform; a short fade stops that clicking. |

Trimming and re-padding gives every clip the same lead-in, whatever the source did. That
consistency is what stops one prompt feeling late relative to the others.

## Denoise

`clean.denoise_floor_db` defaults to -45, close to ffmpeg's own -50 default for `afftdn`.

Higher values remove more, and remove it less discriminately. At -25 the filter will
erase a quiet, steady delivery along with the hiss, and it does so silently: the file
still exists, still has the right duration, and plays back as nothing. `clean.max_loss_lu`
catches that case by comparing loudness before and after, and reverts to the unprocessed
clip when cleaning has destroyed the signal.

## Changing any of this

Edit `config/pipeline.json`. Delete a key to fall back to the built-in default. Unknown
keys are rejected at load rather than silently ignored, so a typo does not quietly leave
you on defaults.

To re-render after a change:

```powershell
python scripts\wvs.py normalize --force
```

For a one-off comparison without editing the file:

```powershell
python scripts\wvs.py normalize --lufs -14 --force
```
