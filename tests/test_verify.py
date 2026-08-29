"""Proving an uploaded pack is what was sent.

This is the only check that runs after the bytes leave the machine, so a bug
here is a bug that lets a broken pack look fine. The archive it parses is
downloaded from the internet, which makes the extraction path worth testing for
more than correctness.
"""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from waze_voice import verify, wazepack


def _tar(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _full_pack() -> dict[str, bytes]:
    return {name: b"ID3" + b"\x00" * 128 for name in sorted(wazepack.VALID_FILENAMES)}


class ExtractionTests(unittest.TestCase):
    def test_files_are_extracted_by_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "p.tar.gz"
            archive.write_bytes(_tar({"pack/TurnLeft.mp3": b"ID3"}))
            files = verify._extract(archive, Path(tmp) / "out")
        self.assertEqual([f.name for f in files], ["TurnLeft.mp3"])

    def test_a_traversing_member_cannot_escape_the_directory(self) -> None:
        """The archive comes off the internet, so `..` in a member name is not
        a hypothetical."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "p.tar.gz"
            archive.write_bytes(_tar({"../../escaped.mp3": b"ID3", "TurnLeft.mp3": b"ID3"}))
            out = root / "out"
            files = verify._extract(archive, out)

            self.assertFalse((root.parent / "escaped.mp3").exists())
            self.assertFalse((root / "escaped.mp3").exists())
            for path in files:
                self.assertEqual(path.parent.resolve(), out.resolve())

    def test_a_corrupt_archive_is_a_message_not_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "p.tar.gz"
            archive.write_bytes(b"this is not a tarball")
            with self.assertRaises(SystemExit) as caught:
                verify._extract(archive, Path(tmp) / "out")
        self.assertIn("truncated", str(caught.exception).lower())


class VerdictTests(unittest.TestCase):
    """`ok` decides whether a pack is trusted, so each way it can be false
    needs to actually make it false."""

    def _result(self, **overrides) -> verify.VerifyResult:
        base = verify.VerifyResult(uuid="u", remote_files=["TurnLeft.mp3"])
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_a_clean_result_is_ok(self) -> None:
        self.assertTrue(self._result().ok)

    def test_an_empty_archive_is_not_ok(self) -> None:
        self.assertFalse(self._result(remote_files=[]).ok)

    def test_each_problem_falsifies_the_verdict(self) -> None:
        for field in ("unknown_files", "missing_core", "size_mismatches", "only_local"):
            with self.subTest(field=field):
                self.assertFalse(self._result(**{field: ["x"]}).ok)

    def test_a_silent_clip_alone_does_not_fail_the_pack(self) -> None:
        """Three of eleven real packs ship TickerPoints deliberately silent."""
        self.assertTrue(self._result(silent_files=["TickerPoints.mp3"]).ok)


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.members = _full_pack()
        # Loudness is measured with ffmpeg; these are not real MP3s.
        self.loudness = mock.patch.object(
            verify.media,
            "measure_loudness",
            return_value=mock.Mock(integrated_lufs=-16.0),
        )
        self.loudness.start()
        self.addCleanup(self.loudness.stop)

    def _run(self, local: Path | None = None) -> verify.VerifyResult:
        def fake_download(uuid: str, destination: Path) -> int:
            payload = _tar(self.members)
            destination.write_bytes(payload)
            return len(payload)

        with mock.patch.object(verify, "download", fake_download):
            return verify.run("uuid-1", local_pack=local)

    def test_a_complete_pack_verifies(self) -> None:
        result = self._run()
        self.assertTrue(result.ok, result)
        self.assertEqual(len(result.remote_files), 43)

    def test_a_file_waze_ignores_is_reported(self) -> None:
        self.members["NotAWazeName.mp3"] = b"ID3"
        self.assertIn("NotAWazeName.mp3", self._run().unknown_files)

    def test_a_missing_core_prompt_is_reported(self) -> None:
        self.members.pop("TurnLeft.mp3")
        result = self._run()
        self.assertIn("TurnLeft.mp3", result.missing_core)
        self.assertFalse(result.ok)

    def test_a_size_mismatch_against_the_local_pack_is_caught(self) -> None:
        """The check that catches a placeholder surviving, or an older
        revision being served."""
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            for name in self.members:
                (local / name).write_bytes(b"ID3" + b"\x00" * 999)
            result = self._run(local)
        self.assertTrue(result.compared_against_local)
        self.assertTrue(result.size_mismatches)
        self.assertFalse(result.ok)

    def test_matching_bytes_compare_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            for name, payload in self.members.items():
                (local / name).write_bytes(payload)
            result = self._run(local)
        self.assertEqual(result.size_mismatches, [])
        self.assertEqual(result.only_local, [])
        self.assertTrue(result.ok)

    def test_a_clip_the_upload_dropped_is_reported(self) -> None:
        dropped = self.members.pop("TurnRight.mp3")
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            for name, payload in self.members.items():
                (local / name).write_bytes(payload)
            (local / "TurnRight.mp3").write_bytes(dropped)
            result = self._run(local)
        self.assertIn("TurnRight.mp3", result.only_local)
        self.assertFalse(result.ok)

    def test_a_silent_clip_is_named(self) -> None:
        with mock.patch.object(
            verify.media,
            "measure_loudness",
            return_value=mock.Mock(integrated_lufs=-90.0),
        ):
            result = self._run()
        self.assertEqual(len(result.silent_files), 43)


if __name__ == "__main__":
    unittest.main()
