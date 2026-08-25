# TTS

Entry points for the synthesis step. The full walkthrough is [docs/tts.md](../docs/tts.md).

| Script | Purpose |
| ------ | ------- |
| `generate.py` | Synthesize the phrases missing from your source media. Same as `wvs.py synth`. |
| `prepare_dataset.py` | Build an LJSpeech-style dataset from cleaned clips, and report whether you have enough audio to bother fine-tuning. |
| `train.py` | Fine-tune a Coqui model. Rarely the right tool for a navigation pack; read its docstring first. |

## Install

```powershell
python -m pip install -r requirements-tts.txt
```

That installs **Chatterbox** (Resemble AI), the default backend: zero-shot voice cloning
from about ten seconds of reference audio, MIT licensed including the model weights, on
the same interpreter as the rest of the pipeline. It pulls in PyTorch, so expect a
multi-GB download.

## Default path

```powershell
python tts\generate.py --accept-voice-terms
```

No training run, no dataset, no checkpoint. It builds a speaker reference from your
cleaned clips and generates the missing lines in that voice.

`--model nano` is the fastest variant if you are on CPU and iterating.

## Alternative backends

`--backend xtts` uses Coqui XTTS-v2 via the maintained `coqui-tts` fork. Better
multilingual coverage, but its **weights are non-commercial** and Coqui Inc. no longer
exists to license them otherwise. `--backend finetuned` loads a checkpoint from
`train.py`. Both are optional installs. See [docs/tts.md](../docs/tts.md).

## Rights and consent

Do not train on, or clone, a person, performer, celebrity, or character voice without the
rights and consent that use requires. The step asks you to acknowledge this once and
records a local, Git-ignored receipt.

No model weights, datasets, generated voices, or checkpoints belong in this repository.
`datasets/`, `models/`, and the audio directories are all ignored.

## Skipping it

Synthesis is optional. The pipeline runs without it, and any phrase it would have filled
is listed in the export checklist for you to record in the Waze app instead.
