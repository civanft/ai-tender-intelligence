"""Regression checks for the publication guard; synthetic credentials only."""
import importlib.util
import gzip
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "publication_guard", Path(__file__).with_name("check_publication.py"),
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationGuardTests(unittest.TestCase):
    def test_private_names_are_rejected_even_in_nested_directories(self):
        for name in (
            ".env", "functions/.env.production", "functions/.secret.local",
            "nested/.streamlit/secrets.toml", "android/key.properties",
            "download/key.p8", "nested/id_ed25519", "serviceAccount.json",
            "sample-firebase-adminsdk-a1.json",
            "backup/.ssh/config", "data/processed/tenders.db", "data/raw/notices.json",
            "research-workspace.json",
        ):
            with self.subTest(name=name):
                self.assertTrue(guard.forbidden_path(name))

    def test_public_samples_and_firebase_client_config_are_allowed(self):
        for name in (
            ".env.example", "functions/.secret.local.example",
            "android/key.properties.example", "google-services.json",
            "GoogleService-Info.plist", "lib/firebase_options.dart",
        ):
            with self.subTest(name=name):
                self.assertFalse(guard.forbidden_path(name))

    def test_secret_values_are_detected_without_being_returned(self):
        samples = (
            b"sk-proj-" + b"a" * 45,
            b"ghp_" + b"b" * 36,
            b"-----BEGIN " + b"PRIVATE KEY-----",
        )
        for sample in samples:
            findings = guard.scan_content(b"first line\n" + sample)
            self.assertTrue(findings)
            self.assertTrue(all(line == 2 for _, line in findings))
            self.assertNotIn(sample.decode(), str(findings))

    def test_empty_env_sample_is_not_a_secret(self):
        self.assertEqual(guard.scan_content(b"OPENAI_API_KEY=\n"), [])

    def test_compressed_secrets_are_inspected_and_bombs_rejected(self):
        secret = b"ghp_" + b"b" * 36
        decoded = guard.decoded_content("publication.json.gz", gzip.compress(secret))
        self.assertTrue(guard.scan_content(decoded))
        with patch.object(guard, "MAX_DECODED_BYTES", 16):
            with self.assertRaises(ValueError):
                guard.decoded_content("publication.json.gz", gzip.compress(b"a" * 17))


if __name__ == "__main__":
    unittest.main()
