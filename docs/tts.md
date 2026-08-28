# Synthesis

Filling prompts your source media never said, or building a whole pack from
nothing but text.

There are two routes, and they suit different situations.

| | Hosted API | Local (Chatterbox) |
| --- | --- | --- |
| To install | nothing | PyTorch, multi-GB |
| Needs | an API key | a CPU and patience |
| Voice comes from | the provider's library, or your own cloned voice | ~10 s of your own audio |
| Source media required | none | yes, to clone from |
| Cost | about 1000-1300 characters per pack | free |
| Audio never leaves your machine | no | yes |

If you want a pack in the next five minutes, use the hosted route. If you want
a specific person's voice, or you want nothing leaving your machine, use the
local one.

## Hosted, from nothing

```powershell
$env:OPENAI_API_KEY = "sk-..."
python scripts\wvs.py voices
python scripts\wvs.py quickstart --voice nova
```

`quickstart` generates every prompt, normalizes, validates, and exports a pack
sized for Waze. It skips extraction and cleaning entirely, because generated
audio arrives at spec and there is nothing to cut or de-noise.

```powershell
# Browse a provider's library
python scripts\wvs.py voices --provider elevenlabs --search british

# Only the 20 strictly-required prompts, if budget is desperate
python scripts\wvs.py quickstart --voice nova --core-only

# One unit system, to free up budget
python scripts\wvs.py quickstart --voice nova --units metric
```

Providers are plain HTTPS calls made with the standard library, so the hosted
path adds no dependencies at all. `wvs doctor` shows which keys are set.

### Supported providers

**`openai`** (`OPENAI_API_KEY`) has no voice cloning of any kind, so every voice
it can produce is one OpenAI licenses to you. That makes it the simplest option
to reason about. It also takes plain-English delivery instructions, which suit
navigation prompts:

```json
"synth": {
  "provider_options": { "instructions": "Brisk and clear, like a navigation system." }
}
```

**`elevenlabs`** (`ELEVENLABS_API_KEY`) has a much larger library and supports
cloning. `provider_options` accepts `voice_settings` and `output_format`;
`wav_44100` avoids a lossy generation before our own encode, if your plan
includes it. Its shared library is worth understanding before you search it: only
human-verified professional clones can be listed, and voice names may not contain
"names of public individuals or entities", so searching it for a character by
name returns nothing. Search by archetype instead - "grandpa", "squeaky",
"gloomy monotone".

**`hume`** (`HUME_API_KEY`) is the only provider here that *designs* a voice
rather than picking one. Octave takes a written description as its primary
input, so a preset's `direction` routes straight into it. That is also its one
sharp edge: a description alone is re-interpreted on every request, and 43
prompts each spoken by a slightly different character is a broken pack. Audition
with `voicelab.design_hume`, then `voicelab.save_hume` to freeze the winner, and
use the returned id as the voice.

**`fish`** (`FISH_AUDIO_API_KEY`) is a community model host, and the odd one out:
there is no catalogue. A voice is whatever model id you point at, taken from the
last path segment of a model page URL, so `fish.audio/m/<id>/` becomes
`--voice <id>`. It has no delivery-direction field, so a preset's `direction`
becomes advisory and register comes entirely from the model.

Two things follow from models being user-uploaded. They can be withdrawn, so a
pack is reproducible only while its model stays up - exported audio survives, the
ability to regenerate one line does not. And the rights position is entirely
yours: a large share of the popular models are clones of copyrighted characters
or living performers, uploaded without permission, and Fish's "unlock commercial
rights" flow cannot grant rights the uploader never held. The free tier is
personal, non-commercial use only.

### Filling gaps rather than starting fresh

`quickstart` is `synth` with the rest of the pipeline attached. To fill only the
prompts your recordings are missing, keeping the real voice everywhere else:

```powershell
python scripts\wvs.py synth --backend openai --voice nova --accept-voice-terms
```

That is worth listening to carefully. A synthetic "Recalculating" between two
recorded prompts is very noticeable.

## Local, cloned from your own clips

```powershell
python -m pip install -r requirements-tts.txt
python scripts\wvs.py synth --accept-voice-terms
```

Chatterbox (Resemble AI) conditions on about ten seconds of your cleaned clips
and speaks new lines in that voice, with no training run. MIT licensed including
the weights, so what you generate is yours. Variants via `--model`: `turbo`
(default), `nano` (fastest on CPU), `full`, `multilingual`.

Two other local backends exist: `xtts` (Coqui XTTS-v2, whose **weights are
non-commercial**) and `finetuned` (a checkpoint from `tts/train.py`). See
`waze_voice/steps/synth.py`.

## Which voice you are allowed to use

Provider libraries are licensed to you by the provider. Pick one and you are
done thinking about it.

Cloning is different. Every provider's terms require that you have the rights to
the voice you clone, and this SDK passes a voice id through without being able to
tell the difference. Cloning a performer or a recognisable character engages
copyright, trademark, and personality rights all at once, and the provider's
terms on top. See [LEGAL.md](../LEGAL.md). The step asks you to acknowledge this
once with `--accept-voice-terms`.

## Making it sound right

**Write for the ear.** `tts_text` in [config/phrases.json](../config/phrases.json)
exists for this. `In 500 meters` is spoken as "In five hundred meters", because a
front-end left alone may read the digits singly; `Make a U-turn` drops the hyphen.

**Listen to the whole thing as a route**, not clip by clip:

```powershell
python scripts\wvs.py qa --route chained_maneuvers
```

`AndThen` is the clip to listen hardest to. It has to flow out of one instruction
and into another, and any seam in the pack shows up there.

**Keep it short.** Generated prompts tend to run long, and length is what costs
you against the 0.8 MB budget. `wvs validate` flags anything unusually long.

## Verification status

The provider request shapes, key handling, retry policy, and the whole quickstart
flow are covered by tests with the HTTP layer stubbed and real audio bytes coming
back. What those tests cannot check is whether a vendor still accepts that request
shape today. That needs a key.

## Skipping synthesis entirely

Optional throughout. `wvs run` skips it with one line when nothing is available,
and any unfilled prompt is listed in the export checklist for you to record in
the Waze app instead.
