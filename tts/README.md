# TTS

Entry points for the synthesis step. The full walkthrough is [docs/tts.md](../docs/tts.md).

| Script | Purpose |
| ------ | ------- |
| `generate.py` | Synthesize the phrases missing from your source media. Same as `wvs.py synth`. |
| `prepare_dataset.py` | Build an LJSpeech-style dataset from cleaned clips, and report whether you have enough audio to bother fine-tuning. |
| `train.py` | Fine-tune a model. Rarely the right tool for a navigation pack; read its docstring first. |

## Requirements

Coqui TTS, which supports **Python 3.9 to 3.11 only**. Use a separate virtual environment:

```powershell
py -3.11 -m venv .venv-tts
.venv-tts\Scripts\activate
python -m pip install -r requirements-tts.txt
```

The rest of the pipeline runs on any supported interpreter and does not depend on any of
this. Synthesis is optional throughout: `wvs run` skips it with a clear message when it is
unavailable, and unfilled phrases go into the export checklist for manual recording.

## Default path

```powershell
python tts\generate.py --accept-voice-terms
```

XTTS-v2 conditions on your own cleaned clips and speaks new lines in that voice with no
training run. For a pack's worth of source audio, this beats fine-tuning.

## Rights and consent

Do not train on, or clone, a person, performer, celebrity, or character voice without the
rights and consent that use requires. The step asks you to acknowledge this once and
records a local, Git-ignored receipt.

No model weights, datasets, generated voices, or checkpoints belong in this repository.
`datasets/`, `models/`, and the audio directories are all ignored.
