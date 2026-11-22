import functions_framework
from flask import Flask, jsonify, request


def process_storage_event(event_type, data):
    if not isinstance(data, dict):
        raise ValueError("El evento de Cloud Storage no contiene datos válidos.")

    bucket = data.get("bucket")
    object_name = data.get("name")
    if not bucket or not object_name:
        raise ValueError("El evento no incluye el bucket y el nombre del objeto.")

    print(f"Event type: {event_type}")
    print(f"Bucket: {bucket}")
    print(f"Object: {object_name}")
    print(f"Generation: {data.get('generation')}")


@functions_framework.cloud_event
def handle_storage_event(cloud_event):
    print("HOLA MUNDO con CodeBuild")
    """Handler para la Cloud Function Gen 2 activada por Eventarc."""
    process_storage_event(cloud_event["type"], cloud_event.data)


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
        process_storage_event(event_type, event_data)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    return jsonify(status="event received"), 200
