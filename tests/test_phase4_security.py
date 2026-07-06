import importlib
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import db
import security


class SecurityHelpersTest(unittest.TestCase):
    def test_password_hash_verifies_and_rejects_wrong_password(self):
        stored = security.hash_password("correct horse battery staple")

        self.assertTrue(security.verify_password("correct horse battery staple", stored))
        self.assertFalse(security.verify_password("wrong password", stored))
        self.assertIn("pbkdf2_sha256", stored)


class OwnershipApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db.DATA_DIR = Path(self.tmp.name)
        db.DB_PATH = Path(self.tmp.name) / "notes.db"
        for module_name in ["main"]:
            sys.modules.pop(module_name, None)
        self.main = importlib.import_module("main")
        self.main.db.DATA_DIR = db.DATA_DIR
        self.main.db.DB_PATH = db.DB_PATH
        self.main.startup()
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()
        sys.modules.pop("main", None)

    def _signup(self, email):
        response = self.client.post(
            "/api/auth/signup",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["user"]

    def test_second_user_cannot_read_first_users_lecture_by_id(self):
        user_a = self._signup("a@example.com")
        session_id = db.save_session(
            "Private lecture",
            "This is private transcript text.",
            "Private summary",
            0,
            source_type="text",
            status="completed",
            user_id=user_a["id"],
        )

        owned = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(owned.status_code, 200, owned.text)

        self._signup("b@example.com")
        direct_probe = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(direct_probe.status_code, 404, direct_probe.text)

    def test_first_account_claims_legacy_sessions(self):
        legacy_id = db.save_session(
            "Old local lecture",
            "Legacy transcript",
            "Legacy summary",
            0,
            source_type="text",
            status="completed",
        )

        user = self._signup("first@example.com")
        migrated = db.get_session(legacy_id, user_id=user["id"])

        self.assertIsNotNone(migrated)
        self.assertEqual(migrated["title"], "Old local lecture")


if __name__ == "__main__":
    unittest.main()
