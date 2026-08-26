"""Hosted TTS providers, and the build-a-pack-from-nothing path.

No network. The HTTP layer is stubbed, which lets everything except the vendor
round trip be checked: URL and payload construction, key handling, retry policy,
and the full quickstart flow producing a real, correctly-named, in-budget pack
from real audio bytes.

What this cannot check is whether the vendor still accepts that request shape.
That needs a key. See docs/tts.md.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from waze_voice import config as config_module
from waze_voice import console, media, paths, providers
from waze_voice.steps import synth

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None


def _mp3_bytes(seconds: float = 1.0, frequency: int = 300) -> bytes:
    """Real MP3 bytes, so the pipeline downstream has something genuine to work on."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clip.mp3"
        media.run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration={seconds}:sample_rate=44100",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(out),
            ]
        )
        return out.read_bytes()


class RegistryTests(unittest.TestCase):
    def test_known_providers(self) -> None:
        self.assertIn("elevenlabs", providers.NAMES)
        self.assertIn("openai", providers.NAMES)

    def test_unknown_provider_lists_the_real_ones(self) -> None:
        with self.assertRaises(providers.ProviderError) as caught:
            providers.get("nonesuch")
        self.assertIn("elevenlabs", str(caught.exception))

    def test_missing_key_names_the_variable_and_where_to_get_one(self) -> None:
        with (
            mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}, clear=False),
            self.assertRaises(providers.ProviderError) as caught,
        ):
            providers.ElevenLabs.from_env()
        message = str(caught.exception)
        self.assertIn("ELEVENLABS_API_KEY", message)
        self.assertIn("elevenlabs.io", message)

    def test_available_reflects_the_environment(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            self.assertEqual(providers.available(), ["openai"])
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(providers.available(), [])


class ElevenLabsRequestTests(unittest.TestCase):
    """The request shape is the part that breaks when a vendor moves."""

    def setUp(self) -> None:
        self.calls: list[dict] = []

        def capture(url, *, headers, payload=None, method="GET"):
            self.calls.append(
                {"url": url, "headers": headers, "payload": payload, "method": method}
            )
            if "/v1/voices" in url:
                return json.dumps(
                    {
                        "voices": [
                            {
                                "voice_id": "abc123",
                                "name": "Narrator",
                                "description": "Warm",
                                "labels": {"accent": "british", "age": "middle aged"},
                            },
                            {"voice_id": "", "name": "Broken"},
                        ]
                    }
                ).encode("utf-8")
            return b"ID3-audio-bytes"

        self.patcher = mock.patch.object(providers, "_request", side_effect=capture)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()

    def test_synthesize_posts_to_the_voice_endpoint(self) -> None:
        provider = providers.ElevenLabs("key-1")
        with tempfile.TemporaryDirectory() as tmp:
            provider.synthesize("Turn left", "abc123", Path(tmp) / "out.mp3")

        call = self.calls[-1]
        self.assertEqual(call["method"], "POST")
        self.assertIn("/v1/text-to-speech/abc123", call["url"])
        self.assertIn("output_format=mp3_44100_128", call["url"])
        self.assertEqual(call["headers"]["xi-api-key"], "key-1")
        self.assertEqual(call["payload"]["text"], "Turn left")
        self.assertEqual(call["payload"]["model_id"], "eleven_multilingual_v2")

    def test_voice_id_is_url_quoted(self) -> None:
        provider = providers.ElevenLabs("key-1")
        with tempfile.TemporaryDirectory() as tmp:
            provider.synthesize("hi", "weird id/../x", Path(tmp) / "out.mp3")
        self.assertNotIn("/../", self.calls[-1]["url"])

    def test_options_pass_through(self) -> None:
        provider = providers.ElevenLabs(
            "key-1",
            model="eleven_turbo_v2_5",
            options={"output_format": "wav_44100", "voice_settings": {"stability": 0.4}},
        )
        self.assertEqual(provider.extension, ".wav")
        with tempfile.TemporaryDirectory() as tmp:
            provider.synthesize("hi", "abc", Path(tmp) / "out.wav")
        call = self.calls[-1]
        self.assertIn("output_format=wav_44100", call["url"])
        self.assertEqual(call["payload"]["model_id"], "eleven_turbo_v2_5")
        self.assertEqual(call["payload"]["voice_settings"], {"stability": 0.4})

    def test_list_voices_parses_and_drops_broken_entries(self) -> None:
        voices = providers.ElevenLabs("key-1").list_voices()
        self.assertEqual([v.id for v in voices], ["abc123"])
        self.assertEqual(voices[0].name, "Narrator")
        self.assertIn("british", voices[0].summary)

    def test_audio_is_written_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "out.mp3"
            providers.ElevenLabs("key-1").synthesize("hi", "abc", out)
            self.assertEqual(out.read_bytes(), b"ID3-audio-bytes")


class OpenAIRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[dict] = []
        self.patcher = mock.patch.object(
            providers,
            "_request",
            side_effect=lambda url, **kw: self.calls.append({"url": url, **kw}) or b"audio",
        )
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()

    def test_speech_endpoint_and_bearer_auth(self) -> None:
        provider = providers.OpenAI("sk-test")
        with tempfile.TemporaryDirectory() as tmp:
            provider.synthesize("Turn right", "nova", Path(tmp) / "o.mp3")
        call = self.calls[-1]
        self.assertEqual(call["url"], "https://api.openai.com/v1/audio/speech")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(call["payload"]["voice"], "nova")
        self.assertEqual(call["payload"]["input"], "Turn right")
        self.assertEqual(call["payload"]["response_format"], "mp3")

    def test_instructions_and_speed_are_optional(self) -> None:
        provider = providers.OpenAI("sk", options={"instructions": "brisk", "speed": 1.1})
        with tempfile.TemporaryDirectory() as tmp:
            provider.synthesize("hi", "nova", Path(tmp) / "o.mp3")
        payload = self.calls[-1]["payload"]
        self.assertEqual(payload["instructions"], "brisk")
        self.assertEqual(payload["speed"], 1.1)

    def test_voice_catalogue_needs_no_key_or_network(self) -> None:
        voices = providers.OpenAI("").list_voices()
        self.assertTrue(any(v.id == "nova" for v in voices))
        self.assertFalse(providers.OpenAI.supports_voice_listing)


class RetryPolicyTests(unittest.TestCase):
    """Retry what is transient; fail fast on what is not."""

    def _http_error(self, code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError("http://x", code, "boom", {}, None)

    def test_bad_key_fails_immediately(self) -> None:
        opener = mock.Mock(side_effect=self._http_error(401))
        with (
            mock.patch.object(providers.urllib.request, "urlopen", opener),
            self.assertRaises(providers.ProviderError) as caught,
        ):
            providers._request("http://x", headers={})
        self.assertEqual(opener.call_count, 1, "a wrong key should not be retried")
        self.assertIn("API key", str(caught.exception))

    def test_unknown_voice_fails_immediately(self) -> None:
        opener = mock.Mock(side_effect=self._http_error(404))
        with (
            mock.patch.object(providers.urllib.request, "urlopen", opener),
            self.assertRaises(providers.ProviderError) as caught,
        ):
            providers._request("http://x", headers={})
        self.assertEqual(opener.call_count, 1)
        self.assertIn("voice id", str(caught.exception))

    def test_rate_limit_is_retried(self) -> None:
        opener = mock.Mock(side_effect=self._http_error(429))
        with (
            mock.patch.object(providers.urllib.request, "urlopen", opener),
            mock.patch.object(providers.time, "sleep"),
            self.assertRaises(providers.ProviderError),
        ):
            providers._request("http://x", headers={})
        self.assertEqual(opener.call_count, providers.MAX_ATTEMPTS)

    def test_a_retry_that_succeeds_returns_the_body(self) -> None:
        good = mock.MagicMock()
        good.__enter__.return_value.read.return_value = b"ok"
        opener = mock.Mock(side_effect=[self._http_error(503), good])
        with (
            mock.patch.object(providers.urllib.request, "urlopen", opener),
            mock.patch.object(providers.time, "sleep"),
        ):
            self.assertEqual(providers._request("http://x", headers={}), b"ok")


class BackendWiringTests(unittest.TestCase):
    def test_hosted_backends_are_registered(self) -> None:
        for name in providers.NAMES:
            self.assertIn(name, synth.BACKENDS)

    def test_hosted_backends_need_no_reference_audio(self) -> None:
        """This is what allows a pack with no source media at all."""
        for name in providers.NAMES:
            self.assertFalse(synth.needs_reference_audio(name))
        for name in synth.LOCAL_BACKENDS:
            self.assertTrue(synth.needs_reference_audio(name))

    def test_availability_follows_the_api_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            ok, reason = synth.is_available("openai")
            self.assertFalse(ok)
            self.assertIn("OPENAI_API_KEY", reason)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk"}, clear=True):
            self.assertEqual(synth.is_available("openai"), (True, ""))

    def test_missing_voice_says_how_to_find_one(self) -> None:
        cfg = config_module.PipelineConfig(
            synth=config_module.SynthConfig(backend="openai", voice="")
        )
        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk"}, clear=False),
            self.assertRaises(SystemExit) as caught,
        ):
            synth.load_backend(cfg, "openai")
        self.assertIn("wvs.py voices", str(caught.exception))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required")
class QuickstartTests(unittest.TestCase):
    """A whole pack from a voice id, with no source media on disk anywhere."""

    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous = os.environ.get(paths.AUDIO_ROOT_ENV)
        os.environ[paths.AUDIO_ROOT_ENV] = str(self.root / "audio")
        paths.ensure_dirs()
        self.audio = _mp3_bytes()

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        else:
            os.environ[paths.AUDIO_ROOT_ENV] = self.previous
        console.set_quiet(False)
        self.tmp.cleanup()

    def test_quickstart_builds_a_valid_pack_from_nothing(self) -> None:
        from waze_voice import cli, wazepack
        from waze_voice.steps import export

        # Nothing on disk to start from: no source media, no CSV, no clips.
        self.assertEqual(list((self.root / "audio" / "extracted").glob("*")), [])

        consent = self.root / synth.CONSENT_RECEIPT
        env = {"OPENAI_API_KEY": "sk-test"}
        with (
            mock.patch.dict(os.environ, env, clear=False),
            mock.patch.object(providers, "_request", return_value=self.audio),
            mock.patch.object(synth, "check_consent", return_value=None),
        ):
            code = cli.main(
                ["quickstart", "--provider", "openai", "--voice", "nova", "--quiet"]
            )
        self.assertFalse(consent.exists())
        self.assertEqual(code, 0)

        pack_dir = paths.export_dir() / export.PACK_DIRNAME
        names = {path.name for path in pack_dir.glob("*.mp3")}
        self.assertTrue(names, "quickstart produced no clips")

        # Every file must be a name Waze recognises, or it is silently ignored.
        self.assertEqual(wazepack.unknown_filenames(names), set())

        manifest = json.loads(
            (paths.export_dir() / export.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertTrue(manifest["budget"]["within_budget"])
        on_disk = sum(path.stat().st_size for path in pack_dir.glob("*.mp3"))
        self.assertEqual(on_disk, manifest["budget"]["total_bytes"])

        # Core prompts in both unit systems, which is what makes a pack usable.
        for units in ("metric", "imperial"):
            missing = wazepack.core_filenames(units) - names
            self.assertEqual(missing, set(), f"{units} core prompts missing: {missing}")

    def test_generated_clips_are_marked_as_synthesized(self) -> None:
        from waze_voice import cli
        from waze_voice import manifest as manifest_module

        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False),
            mock.patch.object(providers, "_request", return_value=self.audio),
            mock.patch.object(synth, "check_consent", return_value=None),
        ):
            cli.main(["quickstart", "--provider", "openai", "--voice", "nova", "--quiet"])

        build = manifest_module.Manifest.load()
        record = build.get("turn_left")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.origin, manifest_module.ORIGIN_SYNTHESIZED)
        self.assertEqual(record.synth_backend, "openai")

    def test_quickstart_without_a_voice_explains_how_to_pick_one(self) -> None:
        from waze_voice import cli

        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False),
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main(["quickstart", "--provider", "openai", "--quiet"])
        self.assertIn("voices", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
