# Synthesis

Filling the phrases your source media never said.

A recording of someone talking rarely contains "Recalculating" or "In 500 meters". The
synthesis step generates those lines in the voice of the clips you already extracted.

## Before anything else

This clones a voice. Confirm you have the rights, and where a real person is involved the
consent, for what you intend to do with the result. [LEGAL.md](../LEGAL.md) has the
detail. The step asks you to acknowledge this once with `--accept-voice-terms` and records
a local, Git-ignored receipt.

## The Python version problem

**Coqui TTS supports Python 3.9 to 3.11. It does not install on 3.12 or newer.**

The rest of the pipeline has no such constraint, so the clean answer is a second virtual
environment used only for this step:

```powershell
py -3.11 -m venv .venv-tts
.venv-tts\Scripts\activate
python -m pip install -r requirements-tts.txt
python -m pip list | findstr TTS
```

Run the synthesis step from that environment, and everything else from your normal one.
Both read and write the same `audio/` directories, so nothing needs copying between them.

If `py -3.11` reports nothing, install Python 3.11 alongside your current version:

```powershell
winget install Python.Python.3.11
```

`python scripts/wvs.py doctor` tells you which situation you are in.

## Two backends

### `xtts` (default)

XTTS-v2 conditions on reference audio at generation time. No training run, no checkpoint,
no GPU strictly required. It needs only a handful of seconds of your voice.

This is the right default for a navigation pack. A pack yields well under a minute of
usable source audio, which is far below what fine-tuning needs and comfortably above what
zero-shot conditioning needs.

```powershell
python scripts\wvs.py synth --accept-voice-terms
```

The step builds the speaker reference itself, taking your longest cleaned clips until it
has about twelve seconds, and concatenating them into one continuous sample. XTTS
conditions better on one continuous sample than on a pile of fragments. Override it with
`--reference my-reference.wav` if you have something better.

The first run downloads model weights. Expect a wait, and a few GB.

### `finetuned`

Loads a checkpoint you trained yourself. Worth it only with a substantial, consistent,
accurately transcribed corpus of one speaker: an audiobook you narrated, a long interview
you own.

```powershell
python tts\prepare_dataset.py
python tts\train.py --dataset datasets\voice --accept-voice-terms
python tts\generate.py --backend finetuned --model-path models\finetune
```

`prepare_dataset.py` writes the LJSpeech layout Coqui's recipes expect and then tells you
how much audio you actually have, along with what that amount supports. Below roughly ten
minutes, fine-tuning generally overfits and sounds worse than zero-shot, and `train.py`
declines to start unless you pass `--force`.

Transcripts come from the `label` and `tts_text` fields in `config/phrases.json`, which is
the one place the text for each clip is already written down. Fix any clip whose audio
does not match its label before training, or the model learns the mismatch.

## Choosing what gets synthesized

By default the step fills required phrases with no audio anywhere. Nothing is regenerated
that already exists.

```powershell
# See what would be generated, without loading a model
python scripts\wvs.py synth --dry-run

# Optional phrases too
python scripts\wvs.py synth --include-optional --accept-voice-terms

# Redo specific phrases
python scripts\wvs.py synth --only recalculating traffic_ahead --force --accept-voice-terms
```

Synthesized clips land in `audio/synthesized/` and are picked up by normalization
alongside everything else.

## Making it sound right

**Write for the ear, not the page.** `tts_text` in `phrases.json` exists for this. The
shipped inventory already uses it: `In 500 meters` is spoken as "In five hundred meters",
because a TTS front-end left to itself may read the digits out one at a time; `Make a
U-turn` drops the hyphen, which front-ends often read as a compound token.

**Listen to every generated line.** Synthetic prompts drift in pace and emphasis more than
cut source audio does, and a prompt that is subtly too slow is genuinely annoying at 70
km/h. The export checklist lists synthesized clips separately for exactly this reason, and
the QA step is where you catch them:

```powershell
python scripts\wvs.py qa --route reroute_and_arrive
```

**More reference audio helps.** Below about six seconds, similarity falls off sharply. If
generated lines do not sound like your source, extract a few more clips before
reaching for other settings.

**GPU is optional but slow to go without.** Set `synth.device` to `cuda` in
`config/pipeline.json` if you have one. CPU generation works; it just takes a while.

## If synthesis is not an option

It is optional throughout. `wvs run` skips it with a clear message when Coqui TTS is
unavailable, and any phrase left unfilled is carried into the export checklist marked for
manual recording. A pack where you record four lines yourself is a perfectly good pack.
