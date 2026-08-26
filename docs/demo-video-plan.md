# Demo video plan

Goal: show a custom navigation voice working on a real device, without
publishing anything you do not have the right to publish.

## Three different things, three different risk profiles

Easy to run together, worth separating:

1. **Building a pack and using it on your own phone.** Personal use.
2. **Publishing a video of it working.** The video contains the audio. Putting it
   on YouTube or in a README distributes that audio, however short the clip.
3. **Publishing the pack itself.** Usually accidental. See below.

Most people intend 1 and 2. The trap is 3.

## The share link is publication

This is easy to miss, and it is specific to how Waze works.

Getting a pack onto a phone means uploading it, which puts it on Waze's servers
behind `https://waze.com/ul?acvp=<UUID>`. Anyone holding that UUID can also fetch
`https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz` and download **every MP3 in
the pack**. Nothing else protects it. The UUID is the only secret.

So if the UUID appears anywhere in your video, you have published the pack, not
just a video of it. Where it leaks:

- The share sheet, if you film yourself sharing the voice.
- A browser address bar, if you open the link on camera.
- Notification previews and the recent-apps switcher.
- A QR code, which is worse: machine-readable straight off the screen.
- Screen recordings, which capture all of the above at full resolution.

Keep the link off camera entirely. Cropping is not enough on a high-resolution
recording; cut those frames.

Also: whatever you name the voice shows up in `Settings > Voice and sound`. Name
it after a character and film that screen, and the name is in the video too.

## If the voice is one you do not own

Honest framing, then it is your call.

A short demonstration clip of a tool sits better than entertainment content: the
purpose is transformative, the amount is a couple of seconds of one-second
prompts, and nobody watches a navigation demo instead of the original. That is
the shape of a fair use argument. It is only ever an argument, decided after the
fact, not a property the video has.

Two things it does not address:

- **Character voices are not only copyright.** A recognisable character carries
  trademark, and a performer's voice can carry personality rights independently
  of who owns the recording. Fair use is a copyright defence; it does not answer
  the other two.
- **Platform enforcement is separate from law.** Content ID and manual claims run
  on their own logic and timeline. A takedown is not a ruling, and you can lose
  the video without ever losing an argument.

Rights holders vary in how actively they pursue this, and children's media
properties tend to be protective.

**This is not legal advice.** If the video matters commercially, or it is going
somewhere with reach, take advice on it rather than on a paragraph in a
repository.

## The version with none of that attached

The demo's actual claim is *"I built a custom navigation voice and here it is
telling me where to go."* That lands with any voice. A recognisable character is
doing rhetorical work, not load-bearing work.

Recording the prompts yourself, or using a voice from someone who agreed, costs
an evening and removes every question above. It also demonstrates the thing you
built, which is the pipeline, rather than the thing you did not, which is the
character.

If you want the demo to be about cloning specifically, clone your own voice from
a few minutes of your own audio. That is a better demonstration of the synthesis
step anyway, because you can play the source and the result back to back.

## Constraints, whatever voice you use

- Under 60 seconds.
- No downloadable pack, and no share link or UUID on screen.
- No implication of official affiliation with Waze, Google, or any rights holder.
- Link to this repository, not to a voice pack.
- Do not commit the video, or its audio, to this repository.

## Shot list

1. Terminal: `wvs run`, ending on the size report against the Waze budget.
2. Phone: the custom voice selected in `Settings > Voice and sound`.
3. Navigation: one distance-plus-maneuver instruction, chained the way Waze
   speaks it. This is the money shot, and it is what `qa` exists to get right.
4. One arrival or reroute moment.
5. End card pointing at the repository.

Shot 1 matters more than it looks. Anyone can record prompts into the in-app
recorder. Fitting a pack inside an undocumented 0.8 MB budget with per-clip
bitrate allocation is the part worth showing.
