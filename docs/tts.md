# Synthesis

Filling the phrases your source media never said.

A recording of someone talking rarely contains "Keep right" or "In a quarter mile". The
synthesis step generates those lines in the voice of the clips you already extracted.

## Before anything else

This clones a voice. Confirm you have the rights, and where a real person is involved the
consent, for what you intend to do with the result. [LEGAL.md](../LEGAL.md) has the
detail. The step asks you to acknowledge this once with `--accept-voice-terms` and records
a local, Git-ignored receipt.

## Install

```powershell
python -m pip install -r requirements-tts.txt
python scripts\wvs.py doctor
```

That installs **Chatterbox**, the default backend. It pulls in PyTorch, so expect a
multi-GB download. No separate Python version or virtual environment is needed: it
installs on the same interpreter as the rest of the pipeline, Python 3.10 through 3.13.

For a CUDA build, install torch from the
[PyTorch selector](https://pytorch.org/get-started/locally/) first, then run the command
above. CPU works fine for a voice pack, which is a handful of one-second clips.

## Generate

```powershell
python scripts\wvs.py synth --accept-voice-terms
```

That is the whole thing. It finds every required phrase with no audio anywhere, builds a
speaker reference from your cleaned clips, and generates the missing lines.

The first run downloads model weights. Subsequent runs are fast.

```powershell
# See what would be generated, without loading a model
python scripts\wvs.py synth --dry-run

# Optional phrases too
python scripts\wvs.py synth --include-optional --accept-voice-terms

# Redo specific phrases
python scripts\wvs.py synth --only and_then traffic_ahead --force --accept-voice-terms

# Fastest variant, for CPU-only machines
python scripts\wvs.py synth --model nano --accept-voice-terms
```

Synthesized clips land in `audio/synthesized/` and are picked up by normalization
alongside everything else.

## Why Chatterbox

| | Chatterbox | Coqui XTTS-v2 | F5-TTS |
| --- | --- | --- | --- |
| Weights licence | **MIT** | Coqui Public Model License | CC-BY-NC |
| Commercial use | Yes | **No** | **No** |
| Python 3.13 | Yes | Yes (via the `coqui-tts` fork) | Unclear |
| Cloning reference needed | ~10 s | ~6 s | ~10 s |
| Maintained by | Resemble AI | Community fork | Community |

The deciding factor is licensing, not Python versions. XTTS-v2's weights are under the
Coqui Public Model License, which permits **non-commercial use only**, and Coqui Inc. shut
down in January 2024, so there is nobody left who can sell you a commercial licence. The
`coqui.ai/cpml` URL printed on the model card is now a dead link. F5-TTS has the same
problem via CC-BY-NC on its pretrained weights.

For an SDK whose whole premise is "bring audio you have the right to use", shipping a
default that quietly caps every output at non-commercial would be a poor choice.
Chatterbox is MIT including the weights, so what you generate is yours.

It also embeds [PerTh](https://github.com/resemble-ai/perth) watermarking in everything it
generates, which means synthetic clips from this pipeline stay detectable downstream. For
a tool that clones voices, that is a feature.

### Model variants

Set `synth.model` in [config/pipeline.json](../config/pipeline.json), or pass `--model`:

| Variant | Size | Notes |
| ------- | ---- | ----- |
| `turbo` | 350M | Default. English, low latency. |
| `nano` | 110M | Fastest on CPU. Lower quality; good when you are iterating. |
| `full` | 500M | English, highest quality of the English models. |
| `multilingual` | 500M | 23+ languages. Set `synth.language` too. |

Generation knobs such as `exaggeration` and `cfg_weight` go in
`synth.generate_options`, which is passed straight through to the backend:

```json
"synth": {
  "model": "turbo",
  "generate_options": { "exaggeration": 0.4 }
}
```

That field is deliberately open-ended so a backend renaming or adding a parameter does not
require a change to this SDK.

## The other backends

Both are optional and neither is installed by default.

### `xtts`

Coqui XTTS-v2 through the community-maintained `coqui-tts` fork. Worth it for languages
Chatterbox does not cover well.

```powershell
python -m pip install coqui-tts
python scripts\wvs.py synth --backend xtts --accept-voice-terms
```

The step prints a licence warning every time it loads, because the non-commercial
restriction on the weights is easy to forget once the audio sounds good.

Note the package name: the original `TTS` package from Coqui is archived and does cap at
Python 3.11. `coqui-tts` is the maintained fork and supports 3.10 through 3.14.

### `finetuned`

A checkpoint you trained yourself. Rarely the right tool here.

```powershell
python tts\prepare_dataset.py
python tts\train.py --dataset datasets\voice --accept-voice-terms
python tts\generate.py --backend finetuned --model-path models\finetune
```

`prepare_dataset.py` writes the LJSpeech layout Coqui's recipes expect and reports how much
audio you actually have. Below roughly ten minutes, fine-tuning overfits and sounds worse
than zero-shot, and `train.py` declines to start unless you pass `--force`.

Chatterbox has no official fine-tuning path, so this trains a Coqui model, which means
inheriting Coqui's weight licensing. Read the table above before going down this road.

## Making it sound right

**Write for the ear, not the page.** `tts_text` in
[config/phrases.json](../config/phrases.json) exists for this. The shipped inventory
already uses it: `In 200 meters` is spoken as "In two hundred meters", because a TTS
front-end left to itself may read the digits out one at a time; `Make a U-turn` drops the
hyphen, which front-ends often read as a compound token.

**Listen to every generated line.** Synthetic prompts drift in pace and emphasis more than
cut source audio does, and a prompt that is subtly too slow is genuinely annoying at 70
km/h. The export checklist lists synthesized clips separately for exactly this reason, and
the QA step is where you catch them:

```powershell
python scripts\wvs.py qa --route chained_maneuvers
```

**More reference audio helps.** Below about six seconds, similarity falls off sharply. The
step warns you when it has less than that. If generated lines do not sound like your
source, extract a few more clips before reaching for other settings.

You can supply your own reference instead of the automatic one:

```powershell
python scripts\wvs.py synth --reference my-best-10-seconds.wav --accept-voice-terms
```

## If you skip synthesis entirely

It is optional throughout, and nothing else in the pipeline depends on it.

- `wvs run` probes for the backend first and skips the step with one line explaining why,
  then carries on through normalize, validate, and export.
- `wvs synth` on its own exits with install instructions rather than a stack trace.
- Any phrase left unfilled is carried into `UPLOAD_CHECKLIST.md` under "Missing, and
  worth fixing". Waze falls back to its default voice for anything absent.
- `wvs run --no-tts` skips the step without probing at all.

A pack where you record four lines yourself is a perfectly good pack.
