# Security

## Reporting a vulnerability

Use GitHub's [private vulnerability reporting](../../security/advisories/new) rather
than a public issue. If that is unavailable, open an issue saying only that you
have a security report and asking for a contact route. Do not put the details in
a public issue.

Expect an acknowledgement within a week.

## What is in scope

This is a local command line tool. It has no server, no network listener, and no
authentication. The realistic attack surface is small but not empty:

- **Path handling.** The tool takes file paths from a CSV and from command line
  flags, and it deletes recursively when rebuilding an export. `--export-dir`
  refuses to remove files it did not create unless `--force` is passed. A way to
  make it delete something outside the directory it was pointed at is a bug worth
  reporting.
- **Subprocess invocation.** Every ffmpeg, Demucs, and TTS call goes through
  `waze_voice/media.py` as an argument list, never a shell string. A path or a
  config value that escapes into shell interpretation would be a real finding.
- **Config and inventory parsing.** `config/*.json` and the source CSV are parsed
  with the standard library. Unknown keys are rejected rather than ignored.
  Filenames in the inventory are required to be bare names, not paths, so a
  traversal through `filename` or `waze_filename` would be a bug.
- **Optional dependencies.** Demucs and the TTS backends download model weights
  from third-party hosts on first use. Those downloads are not verified by this
  project beyond whatever the libraries do themselves. Treat model weights the
  way you would treat any other third-party binary.

## What is out of scope

- The behaviour of Waze, its servers, or its share links. This project does not
  control any of that and reports about it belong to Waze.
- The community upload tooling at `pipeeeeees/waze-voicepack-links`. Report those
  to that project.
- Audio you supply. If you point the tool at a malicious media file, it is ffmpeg
  that parses it; report parser bugs upstream to FFmpeg.
- Rights and licensing questions. Those are real, but they are not security
  issues. See [LEGAL.md](LEGAL.md).

## A note on what this tool does

It clones voices and it publishes packs to a third-party service when you upload
one. Neither is a vulnerability, but both are worth being deliberate about. The
synthesis step asks you to acknowledge that you have the rights and consent for
the voice you are cloning, and the export step tells you plainly that uploading
publishes the result behind a shareable link.
