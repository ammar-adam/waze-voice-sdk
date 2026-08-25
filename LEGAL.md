# Legal Notes

This repository is for building a generic voice navigation audio workflow. It does not grant rights to any third-party media, character, actor, performer, brand, trademark, or voice.

## Do Not Commit

- Copyrighted source media.
- Extracted clips from movies, shows, games, podcasts, or music.
- Synthesized voices based on people or characters without permission.
- Trained model weights based on restricted voices.
- Demo videos containing rights-sensitive audio unless you have clearance to publish them.
- Finished voice packs containing audio you cannot redistribute.

## User Responsibility

You are responsible for making sure your source material, generated audio, and published demos are lawful and permitted by the relevant rights holders, platforms, and local laws.

For public examples, prefer:

- Your own recorded voice.
- Voices from people who gave explicit permission.
- Public-domain or permissively licensed material.
- Synthetic voices with clear commercial and redistribution rights.

## Affiliation

This project is not affiliated with Waze, Google, or any navigation app provider.

## Voice Synthesis

The synthesis step clones a voice from the reference audio you supply. Cloning a voice raises questions that copyright alone does not answer.

Before using it, satisfy yourself that you have:

- The rights to the source recordings you are conditioning on.
- Where a real person's voice is involved, that person's consent for this specific use. Several jurisdictions treat a voice as a protected personal attribute independently of who owns the recording, and some now have statutes aimed squarely at synthetic voice replicas.
- Permission that covers what you actually intend to do. Consent to make something for yourself is not consent to publish it.

The step asks you to acknowledge this once with `--accept-voice-terms` and records a local receipt. The receipt is a prompt to think, not a legal finding, and it is not evidence of anything.

Do not synthesize a performer, celebrity, or fictional character without the rights and consent that use requires.

## Tooling Versus Output

The MIT license in `LICENSE` covers the tooling in this repository. It grants no rights to any media you process, any voice you synthesize, or any pack you produce. Those are governed by whatever terms apply to your source material.

## Not Legal Advice

This file describes the project's position on what belongs in the repository. It is not legal advice. If a use matters to you, take advice on it.
