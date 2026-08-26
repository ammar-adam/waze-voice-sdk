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

## The three shipped presets

| Preset | Source work | Voice | Register |
| ------ | ----------- | ----- | -------- |
| `eeyore` | Winnie-the-Pooh (Milne, 1926) | `openai/ash` @0.92x | Flat, resigned, entirely correct |
| `pooh` | Winnie-the-Pooh (Milne, 1926) | `openai/fable` @0.95x | Gentle, unhurried, slightly muddled |
| `tigger` | The House at Pooh Corner (Milne, 1928) | `openai/nova` @1.12x | Fast, bouncy, overconfident |

Tigger comes from the **1928** book, not the 1926 one. He does not appear in the
first book at all, and the two entered the US public domain two years apart. That
is exactly the kind of distinction a preset's metadata exists to record.

```powershell
python scripts\wvs.py presets show eeyore --lines
```

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

Two rules are enforced by the schema and the validator, not by asking nicely.

### 1. Never a cloned performance

Public domain attaches to a **work**. It never attaches to a later performance of
that work. A 1926 book being public domain says nothing about any recording of
any actor reading it, and an audio likeness of a performer carries their own
rights regardless of the text's age.

So a preset names a catalogue voice and describes delivery. It has **no field for
reference audio**, and the validator rejects any attempt to route one through
`provider_options`:

```
$ python scripts/wvs.py presets check my-preset
  [error] my-preset: 1 problem(s)
  provider_options contains voice-cloning key(s): speaker_wav.
  Presets never clone a performance.
```

This is why the shipped presets target `openai`, which has no voice cloning of
any kind. Every voice it can produce is one OpenAI licenses to you.

### 2. Every line still has to work as navigation

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
- [ ] **Jurisdiction.** Public domain is not global. The Milne books are public
      domain in the United States and are still in copyright in the UK and EU
      until 1 January 2027. State the jurisdiction your basis applies to.

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

### 3. Check it

```powershell
python scripts\wvs.py presets check my-preset
```

This is what CI runs. It validates the rights block, refuses cloning fields,
checks every prompt is present and still unambiguous, and enforces the length
limits.

### 4. Build it and listen

```powershell
python scripts\wvs.py quickstart --preset my-preset
python scripts\wvs.py qa --route chained_maneuvers
```

Check the utilisation line. Target is 85% of Waze's cap and the build fails above
92%. A preset with slow delivery produces longer clips than the default voice, so
confirm your own numbers rather than assuming the shipped ones transfer.

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
- Nothing in any of the three presets uses a studio-invented catchphrase. Tigger
  does not say the thing from the song. That song is from 1968 and is not Milne.

Estimated utilisation for all three sits at 82-83%, with Eeyore the largest at
95.8 seconds of audio because he is the slowest. That is the case the 85% target
exists to absorb.
