import logging
import subprocess
import functions_framework
from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def process_storage_event(event_type, data, event_id=None):
    if not isinstance(data, dict):
        raise ValueError("El evento de Cloud Storage no contiene datos válidos.")

    bucket = data.get("bucket")
    object_name = data.get("name")
    if not bucket or not object_name:
        raise ValueError("El evento no incluye el bucket y el nombre del objeto.")

    logger.info(
        "Evento de Cloud Storage recibido: event_id=%s event_type=%s "
        "bucket=%s object=%s generation=%s",
        event_id,
        event_type,
        bucket,
        object_name,
        data.get("generation"),
    )
    return bucket, object_name


@functions_framework.cloud_event
def handle_storage_event(cloud_event):
    """Handler para la Cloud Function Gen 2 activada por Eventarc."""
    logger.info(
        "Inició el handler de Cloud Storage: event_id=%s event_type=%s "
        "event_source=%s",
        cloud_event.get("id"),
        cloud_event.get("type"),
        cloud_event.get("source"),
    )
    logger.info("Verificando versión de GPG: event_id=%s", cloud_event.get("id"))
    try:
        result = subprocess.run(
            ["gpg", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        logger.exception(
            "La verificación de GPG superó 10 segundos: event_id=%s",
            cloud_event.get("id"),
        )
        raise
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.exception(
            "Falló la verificación de GPG: event_id=%s",
            cloud_event.get("id"),
        )
        raise

    version = result.stdout.splitlines()
    if not version:
        raise RuntimeError("GPG no devolvió información de versión.")
    logger.info("Versión de GPG: %s", version[0])
    try:
        bucket, object_name = process_storage_event(
            cloud_event.get("type"),
            cloud_event.data,
            cloud_event.get("id"),
        )
    except ValueError:
        logger.exception(
            "No se pudo procesar el evento de Cloud Storage: event_id=%s",
            cloud_event.get("id"),
        )
        raise

    logger.info(
        "Finalizó el handler de Cloud Storage: event_id=%s bucket=%s object=%s",
        cloud_event.get("id"),
        bucket,
        object_name,
    )


app = Flask(__name__)


@app.get("/healthz")
def health_check():
    return jsonify(status="ok"), 200


@app.post("/")
@app.post("/events")
def receive_event():
    """Endpoint WSGI para ejecutar el servicio directamente con Gunicorn."""
    event = request.get_json(silent=True)
    if not isinstance(event, dict):
        return jsonify(error="Expected a CloudEvent JSON object"), 400

    event_type = request.headers.get("ce-type") or event.get("type")
    event_data = event.get("data", event)
    try:
        process_storage_event(
            event_type,
            event_data,
            request.headers.get("ce-id") or event.get("id"),
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400

    return jsonify(status="event received"), 200
