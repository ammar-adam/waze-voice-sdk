"""Finding or inventing a voice.

The part worth pinning down is provenance. A library entry says who consented
to it existing, and getting that wrong turns "licensed" into "somebody's clone"
silently, which is the one thing this module exists to keep visible.
"""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from waze_voice import providers, voicelab


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


class ProvenanceTests(unittest.TestCase):
    def test_famous_voices_are_licensed(self) -> None:
        voice = voicelab.LibraryVoice(voice_id="v", name="n", category="famous")
        self.assertTrue(voice.consented)
        self.assertEqual(voice.provenance, "licensed")

    def test_professional_voices_are_consented(self) -> None:
        voice = voicelab.LibraryVoice(voice_id="v", name="n", category="professional")
        self.assertTrue(voice.consented)
        self.assertEqual(voice.provenance, "consented")

    def test_everything_else_is_unverified(self) -> None:
        """Including an empty category, which is what a missing field gives."""
        for category in ("high_quality", "community", "", "generated"):
            with self.subTest(category=category):
                voice = voicelab.LibraryVoice(voice_id="v", name="n", category=category)
                self.assertFalse(voice.consented)
                self.assertEqual(voice.provenance, "UNVERIFIED")


class LibrarySearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[str] = []
        payload = {
            "voices": [
                {
                    "voice_id": "abc",
                    "name": "Grandpa",
                    "category": "professional",
                    "gender": "male",
                    "age": "old",
                    "accent": "british",
                    "cloned_by_count": 7,
                },
                {"name": "No id, dropped"},
            ]
        }

        def capture(url, *, headers, payload=None, method="GET"):
            self.calls.append(url)
            return _json({"voices": [dict(v) for v in payload_voices]})

        payload_voices = payload["voices"]
        self.patcher = mock.patch.object(providers, "_request", side_effect=capture)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_search_terms_reach_the_query_string(self) -> None:
        voicelab.search_library("k", search="dozy bear", category="professional")
        url = self.calls[-1]
        self.assertIn("/v1/shared-voices?", url)
        self.assertIn("search=dozy+bear", url)
        self.assertIn("category=professional", url)

    def test_an_entry_without_an_id_is_dropped(self) -> None:
        """It cannot be synthesized with, so returning it is a trap."""
        found = voicelab.search_library("k")
        self.assertEqual([v.voice_id for v in found], ["abc"])
        self.assertEqual(found[0].cloned_by_count, 7)

    def test_page_size_is_capped_at_the_documented_maximum(self) -> None:
        voicelab.search_library("k", page_size=500)
        self.assertIn("page_size=100", self.calls[-1])


class DesignTests(unittest.TestCase):
    def test_previews_are_base64_decoded(self) -> None:
        audio = b"ID3fake-audio"
        payload = _json(
            {
                "previews": [
                    {
                        "generated_voice_id": "g1",
                        "audio_base_64": base64.b64encode(audio).decode(),
                        "duration_secs": 4.5,
                    }
                ]
            }
        )
        with mock.patch.object(providers, "_request", return_value=payload):
            previews = voicelab.design("k", "an elderly, soft, dozy bear")
        self.assertEqual(len(previews), 1)
        self.assertEqual(previews[0].audio, audio)
        self.assertEqual(previews[0].generated_voice_id, "g1")

    def test_the_description_is_what_is_sent(self) -> None:
        sent: dict = {}

        def capture(url, *, headers, payload=None, method="GET"):
            sent.update(payload or {})
            return _json({"previews": []})

        with mock.patch.object(providers, "_request", side_effect=capture):
            voicelab.design("k", "a bouncing striped cat")
        self.assertEqual(sent["voice_description"], "a bouncing striped cat")
        self.assertIn("text", sent, "an audition needs words to say")


class HumeDesignTests(unittest.TestCase):
    def test_generations_become_previews(self) -> None:
        audio = b"ID3hume"
        payload = _json(
            {
                "generations": [
                    {"generation_id": "h1", "audio": base64.b64encode(audio).decode()},
                    {"generation_id": "h2", "audio": base64.b64encode(audio).decode()},
                ]
            }
        )
        with mock.patch.object(providers, "_request", return_value=payload):
            previews = voicelab.design_hume("k", "a gloomy donkey", count=2)
        self.assertEqual([p.generated_voice_id for p in previews], ["h1", "h2"])
        self.assertEqual(previews[0].audio, audio)

    def test_saving_returns_the_reusable_voice_id(self) -> None:
        """Without a saved id every prompt is a slightly different character."""
        with mock.patch.object(providers, "_request", return_value=_json({"id": "voice-9"})):
            self.assertEqual(voicelab.save_hume("k", "h1", "Eeyore"), "voice-9")


class WritePreviewsTests(unittest.TestCase):
    def test_previews_are_written_and_empty_ones_skipped(self) -> None:
        previews = [
            voicelab.DesignPreview(generated_voice_id="a", audio=b"ID3one"),
            voicelab.DesignPreview(generated_voice_id="b", audio=b""),
            voicelab.DesignPreview(generated_voice_id="c", audio=b"ID3two"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            written = voicelab.write_previews(previews, Path(tmp), "pooh")
            self.assertEqual([p.name for p in written], ["pooh__1.mp3", "pooh__3.mp3"])
            self.assertEqual(written[0].read_bytes(), b"ID3one")


if __name__ == "__main__":
    unittest.main()
