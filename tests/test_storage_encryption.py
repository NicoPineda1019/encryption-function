import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from crypto import storage_encryption


class StorageEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.bucket = Mock()
        self.source_blob = Mock()
        self.destination_blob = Mock()
        self.client.bucket.return_value = self.bucket
        self.bucket.blob.side_effect = [
            self.source_blob,
            self.destination_blob,
        ]
        self.source_blob.download_as_bytes.return_value = b"plain data"
        self.gpg = Mock()
        self.gpg.import_keys.return_value = SimpleNamespace(
            fingerprints=["PUBLIC-KEY-FINGERPRINT"]
        )
        self.gpg.encrypt_file.return_value = SimpleNamespace(
            ok=True,
            data=b"encrypted data",
            status="encryption ok",
        )
        self.public_key_path = patch.object(
            storage_encryption,
            "DEFAULT_PUBLIC_KEY_PATH",
            Path("/mock/public-key.asc"),
        )
        self.public_key_path.start()
        self.addCleanup(self.public_key_path.stop)

    @patch.object(storage_encryption.storage, "Client")
    @patch.object(storage_encryption.gnupg, "GPG")
    def test_encrypts_generation_and_uploads_ciphertext(
        self, gpg_constructor, storage_client
    ):
        storage_client.return_value = self.client
        gpg_constructor.return_value = self.gpg

        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value="PUBLIC KEY"
        ):
            with self.assertLogs(storage_encryption.logger, level="INFO") as logs:
                result = storage_encryption.encrypt_storage_object(
                    "input-bucket", "incoming/report.csv", "12345"
                )

        self.assertEqual(result, "encrypted/incoming/report.csv.gpg")
        self.assertTrue(
            any("Inició el cifrado del objeto" in entry for entry in logs.output)
        )
        self.assertTrue(
            any("Objeto cifrado guardado" in entry for entry in logs.output)
        )
        self.client.bucket.assert_called_once_with("input-bucket")
        self.bucket.blob.assert_has_calls(
            [
                call("incoming/report.csv", generation=12345),
                call("encrypted/incoming/report.csv.gpg"),
            ]
        )
        self.source_blob.download_as_bytes.assert_called_once_with()
        gpg_constructor.assert_called_once()
        imported_key = self.gpg.import_keys.call_args.args[0]
        self.assertEqual(imported_key, "PUBLIC KEY")
        input_stream = self.gpg.encrypt_file.call_args.args[0]
        self.assertIsInstance(input_stream, BytesIO)
        self.assertEqual(input_stream.getvalue(), b"plain data")
        self.gpg.encrypt_file.assert_called_once_with(
            input_stream,
            recipients=["PUBLIC-KEY-FINGERPRINT"],
            armor=False,
            always_trust=True,
        )
        self.destination_blob.upload_from_string.assert_called_once_with(
            b"encrypted data",
            content_type="application/octet-stream",
        )

    @patch.object(storage_encryption.storage, "Client")
    @patch.object(storage_encryption.gnupg, "GPG")
    def test_skips_objects_under_encrypted_prefix(
        self, gpg_constructor, storage_client
    ):
        result = storage_encryption.encrypt_storage_object(
            "input-bucket", "encrypted/report.csv.gpg"
        )

        self.assertIsNone(result)
        storage_client.assert_not_called()
        gpg_constructor.assert_not_called()

    @patch.object(storage_encryption.storage, "Client")
    def test_missing_public_key_fails_before_storage_access(self, storage_client):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaises(FileNotFoundError):
                storage_encryption.encrypt_storage_object(
                    "input-bucket", "incoming/report.csv"
                )

        storage_client.assert_not_called()

    @patch.object(storage_encryption.storage, "Client")
    @patch.object(storage_encryption.gnupg, "GPG")
    def test_fails_when_public_key_import_returns_no_fingerprints(
        self, gpg_constructor, storage_client
    ):
        storage_client.return_value = self.client
        self.gpg.import_keys.return_value = SimpleNamespace(fingerprints=[])
        gpg_constructor.return_value = self.gpg

        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value="INVALID KEY"
        ):
            with self.assertRaisesRegex(RuntimeError, "importar la clave pública"):
                storage_encryption.encrypt_storage_object(
                    "input-bucket", "incoming/report.csv"
                )

        self.destination_blob.upload_from_string.assert_not_called()

    @patch.object(storage_encryption.storage, "Client")
    @patch.object(storage_encryption.gnupg, "GPG")
    def test_fails_when_gpg_encryption_fails(self, gpg_constructor, storage_client):
        storage_client.return_value = self.client
        self.gpg.encrypt_file.return_value = SimpleNamespace(
            ok=False,
            data=b"partial ciphertext",
            status="encryption failed",
        )
        gpg_constructor.return_value = self.gpg

        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value="PUBLIC KEY"
        ):
            with self.assertRaisesRegex(RuntimeError, "encryption failed"):
                storage_encryption.encrypt_storage_object(
                    "input-bucket", "incoming/report.csv"
                )

        self.destination_blob.upload_from_string.assert_not_called()

    @patch.object(storage_encryption.storage, "Client")
    @patch.object(storage_encryption.gnupg, "GPG")
    def test_fails_when_gpg_produces_no_ciphertext(
        self, gpg_constructor, storage_client
    ):
        storage_client.return_value = self.client
        self.gpg.encrypt_file.return_value = SimpleNamespace(
            ok=True,
            data=b"",
            status="encryption ok",
        )
        gpg_constructor.return_value = self.gpg

        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value="PUBLIC KEY"
        ):
            with self.assertRaisesRegex(RuntimeError, "sin producir datos"):
                storage_encryption.encrypt_storage_object(
                    "input-bucket", "incoming/report.csv"
                )

        self.destination_blob.upload_from_string.assert_not_called()


if __name__ == "__main__":
    unittest.main()
