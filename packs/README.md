# Packs

One directory per voice. Everything here is Git-ignored: it holds paths to your
own media and the audio built from it.

    python scripts/wvs.py pack new my-voice --label "My voice"
    python scripts/wvs.py pack list
    python scripts/wvs.py run --pack my-voice

Each pack falls back to the shared `config/` files for anything it does not
override, so a pack usually needs only its own `sources.csv`.

Nothing in here should be committed. If you want to keep a pack's *configuration*
under version control, copy `pack.json` and `sources.csv` somewhere else and
un-ignore that path deliberately, having first checked the CSV does not point at
anything private.
