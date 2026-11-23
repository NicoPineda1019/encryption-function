import logging
import tempfile
from io import BytesIO
from pathlib import Path

import gnupg
from google.cloud import storage

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_KEY_PATH = PROJECT_ROOT / "keys" / "keypair.asc"
ENCRYPTED_PREFIX = "encrypted/"


def encrypt_storage_object(
    bucket_name: str,
    object_name: str,
    generation: str | int | None = None,
) -> str | None:
    """Cifra un objeto de Cloud Storage y sube el resultado al mismo bucket.

    Los objetos que ya estén bajo ``encrypted/`` se ignoran para evitar que
    el trigger procese recursivamente su propia salida.
    """
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

    logger.info(
        "Objeto cifrado guardado: gs://%s/%s (origen: gs://%s/%s)",
        bucket_name,
        destination_name,
        bucket_name,
        object_name,
    )
    return destination_name
