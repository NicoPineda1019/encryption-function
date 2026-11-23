import hashlib
import json
import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Optional, Union

import gnupg
from google.cloud import storage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_KEY_PATH = PROJECT_ROOT / "keys" / "keypair.asc"
ENCRYPTED_PREFIX = "encrypted/"
DECRYPTED_PREFIX = "desencrypted/"
METADATA_SUFFIX = "_metadata.json"


def _metadata_object_name(original_name: str) -> str:
    original_path = PurePosixPath(original_name)
    metadata_name = f"{original_path.stem}{METADATA_SUFFIX}"
    return f"{ENCRYPTED_PREFIX}{original_path.with_name(metadata_name)}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_metadata_object(object_name: str) -> bool:
    return object_name.startswith(ENCRYPTED_PREFIX) and object_name.endswith(METADATA_SUFFIX)


def encrypt_storage_object(
    bucket_name: str,
    object_name: str,
    generation: Optional[Union[str, int]] = None,
) -> Optional[str]:
    """Cifra un objeto de Cloud Storage y sube el resultado al mismo bucket.

    Los objetos que ya estén bajo ``encrypted/`` se ignoran para evitar que
    el trigger procese recursivamente su propia salida.
    """
    logger.info(
        "Inició el cifrado del objeto de Cloud Storage: "
        "bucket=%s object=%s generation=%s",
        bucket_name,
        object_name,
        generation,
    )

    if object_name.startswith(ENCRYPTED_PREFIX):
        logger.info("Se omite el objeto cifrado: gs://%s/%s", bucket_name, object_name)
        return None

    public_key_path = Path(DEFAULT_PUBLIC_KEY_PATH)
    if not public_key_path.is_file():
        raise FileNotFoundError(f"No se encontró la clave pública: {public_key_path}")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    source_generation = int(generation) if generation is not None else None
    source_blob = bucket.blob(object_name, generation=source_generation)
    source_data = source_blob.download_as_bytes()

    destination_name = f"{ENCRYPTED_PREFIX}{object_name}.gpg"
    metadata_name = _metadata_object_name(object_name)
    with tempfile.TemporaryDirectory(prefix="gpg-") as gpg_home:
        gpg = gnupg.GPG(gnupghome=gpg_home)
        imported = gpg.import_keys(public_key_path.read_text(encoding="utf-8"))
        if not imported.fingerprints:
            raise RuntimeError("GPG no pudo importar la clave pública de cifrado.")

        encrypted = gpg.encrypt_file(
            BytesIO(source_data),
            recipients=[imported.fingerprints[0]],
            armor=False,
            always_trust=True,
        )
        if not encrypted.ok:
            raise RuntimeError(f"Falló el cifrado GPG: {encrypted.status}")
        if not encrypted.data:
            raise RuntimeError("GPG terminó sin producir datos cifrados.")

        destination_blob = bucket.blob(destination_name)
        destination_blob.upload_from_string(
            encrypted.data,
            content_type="application/octet-stream",
        )

    metadata = {
        "original": {
            "path": f"gs://{bucket_name}/{object_name}",
            "size_bytes": len(source_data),
            "checksum_sha256": _sha256(source_data),
        },
        "encrypted": {
            "path": f"gs://{bucket_name}/{destination_name}",
            "size_bytes": len(encrypted.data),
            "checksum_sha256": _sha256(encrypted.data),
        },
    }
    bucket.blob(metadata_name).upload_from_string(
        json.dumps(metadata, indent=2),
        content_type="application/json",
    )

    logger.info(
        "Objeto cifrado guardado: gs://%s/%s (origen: gs://%s/%s); "
        "metadatos: gs://%s/%s",
        bucket_name,
        destination_name,
        bucket_name,
        object_name,
        bucket_name,
        metadata_name,
    )
    return destination_name


def decrypt_storage_object(
    bucket_name: str,
    object_name: str,
    generation: Optional[Union[str, int]] = None,
) -> Optional[str]:
    """Descifra un objeto bajo ``encrypted/`` y lo guarda bajo ``desencrypted/``."""
    if not object_name.startswith(ENCRYPTED_PREFIX):
        logger.info(
            "Se omite el objeto que no está cifrado: gs://%s/%s",
            bucket_name,
            object_name,
        )
        return None

    if is_metadata_object(object_name):
        logger.info(
            "Se omite el objeto de metadatos: gs://%s/%s",
            bucket_name,
            object_name,
        )
        return None

    encrypted_name = object_name[len(ENCRYPTED_PREFIX):]
    if encrypted_name.endswith(".gpg"):
        encrypted_name = encrypted_name[:-4]
    if not encrypted_name:
        raise ValueError("El objeto cifrado no contiene un nombre de archivo.")

    #passphrase = os.environ.get("GPG_PASSPHRASE")
    passphrase = os.environ.get("GPG_PASSPHRASE", "datos123")
    if not passphrase:
        raise RuntimeError("La variable de entorno GPG_PASSPHRASE no está configurada.")

    private_key_path = Path(DEFAULT_PUBLIC_KEY_PATH)
    if not private_key_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de claves: {private_key_path}"
        )

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    source_generation = int(generation) if generation is not None else None
    source_blob = bucket.blob(object_name, generation=source_generation)
    encrypted_data = source_blob.download_as_bytes()
    metadata_name = _metadata_object_name(encrypted_name)
    metadata_blob = bucket.blob(metadata_name)
    metadata_bytes = metadata_blob.download_as_bytes()
    try:
        metadata = json.loads(metadata_bytes)
        expected_checksum = metadata["original"]["checksum_sha256"]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        raise ValueError(
            f"Metadatos ausentes o inválidos: gs://{bucket_name}/{metadata_name}"
        ) from error
    if not isinstance(expected_checksum, str) or not expected_checksum:
        raise ValueError(
            f"Checksum original inválido en gs://{bucket_name}/{metadata_name}"
        )

    destination_name = f"{DECRYPTED_PREFIX}{encrypted_name}"
    with tempfile.TemporaryDirectory(prefix="gpg-") as gpg_home:
        gpg = gnupg.GPG(gnupghome=gpg_home)
        imported = gpg.import_keys(private_key_path.read_text(encoding="utf-8"))
        if not imported.fingerprints:
            raise RuntimeError("GPG no pudo importar la clave privada de descifrado.")

        decrypted = gpg.decrypt_file(BytesIO(encrypted_data), passphrase=passphrase)
        if not decrypted.ok:
            raise RuntimeError(f"Falló el descifrado GPG: {decrypted.status}")
        if not decrypted.data:
            raise RuntimeError("GPG terminó sin producir datos descifrados.")

        actual_checksum = _sha256(decrypted.data)
        checksum_matches = actual_checksum == expected_checksum
        logger.info(
            "Validación de checksum SHA-256 del archivo descifrado: "
            "resultado=%s esperado=%s calculado=%s archivo=%s",
            "válido" if checksum_matches else "inválido",
            expected_checksum,
            actual_checksum,
            f"gs://{bucket_name}/{object_name}",
        )
        if not checksum_matches:
            raise RuntimeError(
                "El checksum SHA-256 del archivo descifrado no coincide "
                "con los metadatos."
            )

        destination_blob = bucket.blob(destination_name)
        destination_blob.upload_from_string(
            decrypted.data,
            content_type="application/octet-stream",
        )

    logger.info(
        "Objeto descifrado guardado: gs://%s/%s (origen: gs://%s/%s)",
        bucket_name,
        destination_name,
        bucket_name,
        object_name,
    )
    return destination_name
