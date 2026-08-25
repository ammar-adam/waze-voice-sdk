# Waze import spike: findings

Real-device results. Copy the template and fill in one section per device tested.

Keep it factual. Record what you saw, not what you expected. Negative results are as
useful as positive ones: "the directory does not exist on this version" saves the next
person the same twenty minutes.

No findings recorded yet.

---

## Template

### Device

- Device:
- OS version:
- Waze version (`Settings > About`):
- Region:
- Date tested:

### Recorder availability

- [ ] `Settings > Voice and sound > Waze voice > Add a voice` exists
- [ ] Recording a prompt succeeded
- [ ] The recorded prompt played during navigation

If the menu path differed, write the actual path here:

### Prompt list

Which prompts did the app actually ask for, in what order? This is the only way
`config/phrases.json` gets confirmed.

1.
2.
3.

### Direct injection attempt

- [ ] Android: `Android/media/com.waze/` exists and is browsable
- [ ] Android: recordings found on disk

  Path:
  Filename convention:
  Format / sample rate / channels:

- [ ] Replacing a recording with a pre-rendered clip was possible
- [ ] The replaced clip played during navigation
- [ ] iOS: any accessible path found

### Microphone playback

- [ ] Playing an exported clip into the microphone produced an acceptable recording
- Distance used:
- Anything that had to change from the guidance in `VERIFY-IMPORT-FIRST.md`:

### Result

Which outcome, and what would you tell someone starting today?

### Exact steps

1.
2.
3.

### Notes
