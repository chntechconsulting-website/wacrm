import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from database import get_db
from main import app
from models.call_log import CallLog
from models.integration import IntegrationConfig
from routers.ivr import (
    MAX_RECORDING_BYTES,
    _absolute_media_url,
    _looks_like_audio,
    _safe_recording_extension,
)
from services.auth import get_current_user
from services.doocti_recording_service import DooctiRecordingService


class TestMobileRecordingHelpers(unittest.TestCase):
    def test_rejects_text_and_accepts_common_audio_headers(self):
        self.assertFalse(_looks_like_audio(b"<html>not audio</html>"))
        self.assertFalse(_looks_like_audio(b""))

        self.assertTrue(_looks_like_audio(b"ID3" + b"\x00" * 20))
        self.assertTrue(_looks_like_audio(b"RIFF\x24\x00\x00\x00WAVEfmt "))
        self.assertTrue(_looks_like_audio(b"OggS" + b"\x00" * 20))
        self.assertTrue(_looks_like_audio(b"#!AMR\n" + b"\x00" * 20))
        self.assertTrue(_looks_like_audio(b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 8))
        self.assertTrue(_looks_like_audio(b"\xff\xfb\x90\x64" + b"\x00" * 20))

    def test_extension_is_derived_from_name_or_mime(self):
        self.assertEqual(_safe_recording_extension("Call 12.MP3", None), ".mp3")
        self.assertEqual(_safe_recording_extension("recording", "audio/mp4"), ".m4a")
        self.assertEqual(_safe_recording_extension("voice.wav", "audio/wav"), ".wav")
        self.assertIsNone(_safe_recording_extension("notes.txt", "text/plain"))

    def test_local_media_paths_become_absolute(self):
        url = _absolute_media_url("/uploads/recordings/42/call.mp3")
        self.assertTrue(url.startswith("https://"))
        self.assertTrue(url.endswith("/uploads/recordings/42/call.mp3"))
        self.assertEqual(
            _absolute_media_url("https://storage.example.com/call.mp3"),
            "https://storage.example.com/call.mp3",
        )

    def test_mobile_calls_never_probe_doocti_storage(self):
        mobile = CallLog(
            provider="MOBILE_SIM",
            provider_call_id="SIM_123",
            call_status="COMPLETED",
            duration_seconds=30,
        )
        direct = CallLog(
            provider="DIRECT_DIAL",
            provider_call_id="SIM_124",
            call_status="COMPLETED",
            duration_seconds=30,
        )
        self.assertIsNone(
            DooctiRecordingService.match_recording_for_call(mobile, db=None)
        )
        self.assertIsNone(
            DooctiRecordingService.match_recording_for_call(direct, db=None)
        )

    def test_upload_limit_is_documented(self):
        self.assertEqual(MAX_RECORDING_BYTES, 25 * 1024 * 1024)


class TestMobileRecordingUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = cls.temp_dir.name

        db_path = os.path.join(cls.temp_dir.name, "recording_test.db")
        cls.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        CallLog.__table__.create(cls.engine)
        IntegrationConfig.__table__.create(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, role="ADMIN", username="admin"
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        settings.UPLOAD_DIR = cls.old_upload_dir
        cls.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        db = self.Session()
        db.query(CallLog).delete()
        db.commit()
        self.call = CallLog(
            provider="MOBILE_SIM",
            provider_call_id="SIM_TEST_RECORDING",
            from_number="+919876543210",
            to_number="+919876543211",
            call_status="COMPLETED",
            call_direction="OUTBOUND",
            duration_seconds=30,
        )
        db.add(self.call)
        db.commit()
        db.refresh(self.call)
        self.call_id = self.call.id
        db.close()

    def _audio_bytes(self):
        return b"ID3" + b"\x00" * 4096

    def test_upload_links_verified_audio(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            files={"file": ("call.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["recording_url"].endswith(".mp3"))
        self.assertEqual(data["recording_status"], "AVAILABLE")
        self.assertEqual(data["call_source"], "MOBILE")
        self.assertIsNone(data["native_call_reference"])
        self.assertEqual(data["recording_source"], "UPLOAD")

        db = self.Session()
        call = db.query(CallLog).filter(CallLog.id == self.call_id).first()
        stored = call.recording_url
        db.close()
        self.assertTrue(stored.startswith(f"/uploads/recordings/{self.call_id}/"))

    def test_upload_rejects_non_audio(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            files={"file": ("notes.mp3", b"<html>" + b"x" * 4096, "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not a supported audio", response.text)

    def test_upload_marks_device_source(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            data={
                "source": "DEVICE",
                "consent": "true",
                "duration_seconds": "30",
            },
            files={"file": ("call-device.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["recording_source"], "DEVICE")
        self.assertEqual(data["recording_status"], "AVAILABLE")
        self.assertEqual(data["recording_duration_seconds"], 30)
        self.assertIsNotNone(data["recording_consent_at"])
        self.assertIsNotNone(data["recording_verified_at"])
        self.assertEqual(len(data["recording_checksum"]), 64)

    def test_device_upload_requires_explicit_consent(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            data={"source": "DEVICE", "duration_seconds": "30"},
            files={"file": ("call-device.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent is required", response.text)

    def test_device_upload_requires_actual_duration(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            data={"source": "DEVICE", "consent": "true"},
            files={"file": ("call-device.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("duration is required", response.text)

    def test_device_upload_rejects_wrong_duration(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            data={
                "source": "DEVICE",
                "consent": "true",
                "duration_seconds": "5",
            },
            files={"file": ("wrong-call.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("does not match", response.text)

        db = self.Session()
        call = db.query(CallLog).filter(CallLog.id == self.call_id).first()
        self.assertEqual(call.recording_status, "VERIFICATION_FAILED")
        self.assertIsNone(call.recording_url)
        db.close()

    def test_reuploading_identical_bytes_is_idempotent(self):
        first = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            files={"file": ("call.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            files={"file": ("call-copy.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(
            first.json()["recording_url"], second.json()["recording_url"]
        )
        self.assertEqual(second.json()["recording_status"], "AVAILABLE")

    def test_recording_status_can_be_reported_but_not_forced_available(self):
        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording-status",
            json={"status": "PENDING_SYNC", "detail": "Waiting for device file"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recording_status"], "PENDING_SYNC")

        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording-status",
            json={"status": "UPLOAD_FAILED", "detail": "Network error"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recording_status"], "UPLOAD_FAILED")

        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording-status",
            json={"status": "AVAILABLE"},
        )
        self.assertEqual(response.status_code, 400)

    def test_verified_recording_cannot_be_marked_failed(self):
        upload = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording",
            files={"file": ("call.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)

        response = self.client.post(
            f"/api/ivr/calls/{self.call_id}/recording-status",
            json={"status": "UPLOAD_FAILED"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recording_status"], "AVAILABLE")

    def test_upload_rejects_non_mobile_call(self):
        db = self.Session()
        doocti = CallLog(
            provider="DOOCTI",
            provider_call_id="DOOCTI_TEST_RECORDING",
            from_number="1282",
            to_number="+919876543210",
            call_status="COMPLETED",
            duration_seconds=30,
        )
        db.add(doocti)
        db.commit()
        doocti_id = doocti.id
        db.close()

        response = self.client.post(
            f"/api/ivr/calls/{doocti_id}/recording",
            files={"file": ("call.mp3", self._audio_bytes(), "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("only be attached to Mobile SIM", response.text)


if __name__ == "__main__":
    unittest.main()
