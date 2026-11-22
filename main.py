import functions_framework


@functions_framework.cloud_event
def app(cloud_event):
    """Procesa eventos de objetos finalizados en Cloud Storage."""
    data = cloud_event.data
    if not isinstance(data, dict):
        raise ValueError("El evento de Cloud Storage no contiene datos válidos.")

    bucket = data.get("bucket")
    object_name = data.get("name")
    if not bucket or not object_name:
        raise ValueError("El evento no incluye el bucket y el nombre del objeto.")

    print(f"Event type: {cloud_event['type']}")
    print(f"Bucket: {bucket}")
    print(f"Object: {object_name}")
    print(f"Generation: {data.get('generation')}")
