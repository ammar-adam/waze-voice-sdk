# Presets

A preset turns this into a finished pack:

```powershell
python scripts\wvs.py presets list
python scripts\wvs.py quickstart --preset eeyore
```

It bundles three things: a **voice** from a provider's licensed catalogue, a
**delivery direction** describing how to speak, and **all 43 Waze prompts
rewritten in that character's register**.

The rewrite is the point. A generic navigation line read in a different voice is
a novelty. A line actually written in character is the thing people share.

## The shipped presets

They fall into two groups, and the difference is not cosmetic.

**Public domain.** These rest on an expired copyright term, use a licensed
catalogue voice, and can be published without a rights argument.

| Preset | Source work | Voice | Register |
| ------ | ----------- | ----- | -------- |
| `eeyore` | Winnie-the-Pooh (Milne, 1926) | `openai/ash` @0.92x | Flat, resigned, entirely correct |
| `pooh` | Winnie-the-Pooh (Milne, 1926) | `openai/fable` @0.95x | Warm, unhurried, audibly thinking |
| `tigger` | The House at Pooh Corner (Milne, 1928) | `openai/nova` @1.15x / **1.0x** | Fast, bouncy, overconfident |

Tigger comes from the **1928** book, not the 1926 one. He does not appear in the
first book at all, and the two entered the US public domain two years apart. That
is exactly the kind of distinction a preset's metadata exists to record.

**In copyright.** These do not rest on an expired term. Each names a third-party
community model on Fish Audio that is presented as a clone of the original
performance, uploaded by a member of the public without any permission from the
rights holder or the performer.

| Preset | Source | Voice | Register |
| ------ | ------ | ----- | -------- |
| `paddington` | A Bear Called Paddington (Bond, 1958) | `fish/51d1503a...` | Polite, earnest, faintly apologetic |
| `cookie-monster` | Sesame Street (1969) | `fish/a3ec9a07...` | Blunt, greedy, present tense |
| `elmo` | Sesame Street (1980) | `fish/193f7f8f...` | Bright, giggly, third person |

Pooh and Tigger have community models too, and `scripts/build_all.py` uses
them by default so one key covers every character. `--catalogue` builds those
two from their licensed voice instead:

| Preset | Community model |
| ------ | --------------- |
| `pooh` | `cf6e370cb45240b492b14c70a18d0259` |
| `tigger` | `23ad79b4e84f46259dd256c0b01526c2` |

Those two ids live in `build_all.py`, not in the preset files, and deliberately.
`pooh` and `tigger` rest on an expired copyright and their presets should keep
saying so; routing them through a clone changes only how the lines are spoken,
and the run prints that it did.

They are in the repository because people build these anyway, and a pipeline
that quietly omits the rights position is worse than one that records it. What
the SDK gives you here is an accurate label, not permission. The 43 lines in
each are original writing; the character, the name and the voice are not.

```powershell
python scripts\wvs.py presets show eeyore --lines
```

## Two speech rates, where a character needs them

Tigger runs at 1.15x for greetings and the reroute, and drops to **1.0x for
anything a driver acts on**. That split is `critical_provider_options` in the
preset.

The reason is specific: an excited voice at speed makes `ExitLeft` and
`ExitRight` the likeliest pair in the whole pack to be misheard, and a missed
greeting costs nothing where a missed turn costs a junction. The energy survives
the slowdown because it comes from the exclamation in the text and from the
delivery direction, not from the rate.

A prompt counts as navigation-critical if it carries a required token (a
direction, a distance, an exit number) or is heard often enough to matter. That
covers maneuvers, distances, ordinals, alerts, arrival, and `AndThen`; it leaves
the nine drive-start greetings and the reroute chime free to be fast.

Presets that need only one rate, like Eeyore and Pooh, simply omit the field.

## Where the character goes, and where it does not

Not evenly across the 43 prompts. That is a deliberate design decision with two
reasons behind it.

**Budget.** Maneuver and distance prompts carry the highest weight in the size
allocator because they are heard on every instruction. Long lines there cost the
most bytes, and the pack has to fit inside roughly 0.8 MB in total.

**Repetition.** A joke on `TurnLeft.mp3` is funny once and grating by the fourth
turn of the drive.

So the frequently-heard prompts stay tight and the **delivery direction** carries
the register, while the greetings, arrival, alerts, and roundabout ordinals carry
the writing. Eeyore says "Turn left." and the flatness does the work; he says
"take the seventh exit. This roundabout is a lot." where you will hear it once a
year.

Validation enforces the length half of this: prompts of weight 2.0 or above are
capped at 70 characters, everything else at 160.

## The rules, and how they are enforced

Three rules are enforced by the schema and the validator, not by asking nicely.

### 1. A preset cannot carry reference audio

Public domain attaches to a **work**. It never attaches to a later performance of
that work. A 1926 book being public domain says nothing about any recording of
any actor reading it, and an audio likeness of a performer carries their own
rights regardless of the text's age.

So a preset has **no field for reference audio**, and the validator rejects any
attempt to route one through `provider_options`:

```
$ python scripts/wvs.py presets check my-preset
  [error] my-preset: 1 problem(s)
  provider_options contains voice-cloning key(s): speaker_wav.
  Presets never clone a performance.
```

**Be clear about what this does and does not stop.** It stops a preset from
carrying a voice sample and cloning it here. It cannot stop a preset naming a
provider voice id that is *already* a clone somebody else made, because a voice
id is an opaque string and no validator can hear it. The `fish` presets above
are exactly that case. Rule 2 exists because rule 1 has that hole.

### 2. The copyright status has to be stated

`rights.status` is required, and must be `public-domain` or `in-copyright`.
There is no default, so the flattering answer cannot be the one you get by
saying nothing:

```
$ python scripts/wvs.py presets check my-preset
  [error] my-preset: 1 problem(s)
  rights.status must be one of public-domain, in-copyright; got ''.
```

An `in-copyright` preset is a legitimate thing to build, and the validator will
pass it. What it will not do is let the question go unanswered. The status shows
up in `presets list`, in `preflight`, and as a warning at build time, so the
last thing you see before spending money is what you are actually building.

### 3. Every line still has to work as navigation

A driver who has never heard of the character must know exactly what to do.
The validator checks that each line still contains what it exists to
communicate: "left" in a left turn, "quarter mile" in the quarter-mile callout,
"seventh" in the seventh-exit prompt.

Distance callouts are the strictest. Never get cute with a number.

```
$ python scripts/wvs.py presets check my-preset
  in_quarter_mile: 'In a little while, I should think.' does not contain
  'quarter mile' or 'quarter of a mile'. A driver who has never heard of the
  character still has to know what to do.
```

## Adding a preset

### 1. Answer the rights questions first

Both of them, in this order. If either answer is no, stop.

- [ ] **Work level.** Is the *specific work* the character appears in in the
      public domain? Not the character generally, not the franchise, not an
      earlier book in the same series. Name the work, the author, the year, and
      the basis. If you cannot state the basis in one sentence, you do not have
      one yet.
- [ ] **Which work.** If the character appears across several books, which one
      are you drawing on, and is *that* one clear? Tigger and Pooh differ by two
      years for exactly this reason.
- [ ] **Performance level.** Are you using a catalogue voice with written
      direction, and cloning nothing? There is no acceptable version of "just a
      little bit like the film."
- [ ] **Adaptation level.** Is every line drawn from the book character rather
      than a later adaptation? No catchphrases invented by a studio, no songs, no
      characters added later, no dialogue from a film.
- [ ] **Trademark.** Are you aware the character's *name* may be a live
      trademark even where the text's copyright has expired? Trademark does not
      expire. This is the weakest part of the whole arrangement and you should
      know that going in.
- [ ] **Jurisdiction.** Public domain is not global, and you must state which
      country your basis applies to. For the Milne books specifically:

      | Country | Status |
      | ------- | ------ |
      | United States | Public domain. 1926 book from 1 Jan 2022; 1928 book from 1 Jan 2024. |
      | Canada | Public domain since 1 Jan 2007. Milne died 1956 and Canada was life plus 50 then; the 2022 extension to life plus 70 was not retroactive. |
      | UK and EU | **Still in copyright until 1 January 2027** (life plus 70). |

      Anywhere else, check before assuming.

### 2. Write the lines

```powershell
copy presets\eeyore.json presets\my-preset.json
```

- All 43 prompts, no exceptions.
- Frequently-heard prompts stay short. Let the delivery direction carry them.
- Distance callouts keep their numbers exactly.
- Read the chained ones aloud: `in_half_mile` + `turn_right`, and
  `turn_left` + `and_then` + `turn_right`. They have to flow.
- Vary the nine `StartDrive` greetings. They are the cheapest place to be funny.

### 3. Check it, before spending anything

```powershell
python scripts\wvs.py preflight --preset my-preset
```

Pre-flight runs everything that can be checked without an API call: preset
validation, the Waze filename mapping, the clarity rules, and an **estimated**
size against the cap. It also prints what it cannot tell you, which is mostly
real clip duration and how the lines actually sound.

```powershell
python scripts\wvs.py presets check my-preset
```

`presets check` is the narrower validation-only version, and is what CI runs. It validates the rights block, refuses cloning fields,
checks every prompt is present and still unambiguous, and enforces the length
limits.

### 4. Build it and listen

```powershell
python scripts\wvs.py quickstart --preset my-preset
python scripts\wvs.py qa --route chained_maneuvers
```

Check the utilisation line. Target is 85% of Waze's cap and the build fails above
92%. **The build's number is measured from the encoded files**; pre-flight's is an
estimate from character counts. If the two differ by more than 10% the build says
so, which means the estimate reads wrong for that voice and you should trust the
build.

A preset with slow delivery produces longer clips, so confirm your own numbers
rather than assuming the shipped ones transfer.

`chained_maneuvers` is the route to listen to hardest. If anything in the pack
sounds spliced, `AndThen` is where you will hear it.

### 5. Open the pull request

Include:

- The completed rights checklist above, with your answers, not ticks.
- The utilisation figure from your build.
- A note on which prompts you left plain and why.

A preset that fails `presets check` will not be merged. A preset that passes but
whose rights basis is hand-waved will not be merged either.

## Worked example: why Eeyore is written the way it is

The joke is that the directions are perfect and the delivery has given up. That
only survives repetition if the maneuvers stay clipped, so:

- `turn_left` is exactly `"Turn left."` The register is entirely in the delivery
  direction: *"slowly and flatly with a resigned, gloomy affect... a slight
  downward inflection ending every phrase."*
- `arrived` gets `"You've arrived. Well. That's that."` You hear it once.
- `start_drive_4` gets `"Setting off. Thanks for noticing me."` That phrase is
  from the 1926 book, which is the point: it is drawn from the work in the public
  domain, not from a later adaptation.
- Nothing in any of the three public-domain presets uses a studio-invented catchphrase. Tigger
  does not say the thing from the song. That song is from 1968 and is not Milne.

Estimated utilisation for all three sits at 82%, with Pooh and Eeyore around
100 seconds of audio and Tigger at 75. That is the case the 85% target exists to
absorb.

## What was verified, and how

The distance filenames are not guesswork. Eleven real packs were downloaded from
the community archive and transcribed offline; `200.mp3` is confirmed as the
0.1 mile callout, `400.mp3` a quarter mile, `800.mp3` half a mile, `1500.mp3`
one mile. The full method and results are in
[waze-import-spike.md](waze-import-spike.md), including two things it confirmed
by accident: the 43-filename list is exactly right, and real packs sit between
53% and 94% of the size cap.
