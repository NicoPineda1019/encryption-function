# encryption-function
Función para cifrado de archivos

## Despliegue con Google Cloud Build

`codebuild.yml` despliega la Cloud Function `gcp-encryption-cloud-function`
como función Gen 2 activada por Eventarc cuando se finaliza la creación de un
objeto en Cloud Storage (`google.cloud.storage.object.v1.finalized`). Configura
una instancia mínima para reducir los arranques en frío y despliega
`handle_storage_event` como entry point de la función.

El proyecto también expone `app` como aplicación WSGI para ejecución directa
con Gunicorn/Cloud Run. Si se usa ese modo, Eventarc puede enviar el CloudEvent
al endpoint `/` o `/events`; `/healthz` responde para comprobaciones de salud.

Antes de desplegar, reemplaza `REPLACE_WITH_BUCKET_NAME` por el nombre del
bucket y ajusta `_TRIGGER_LOCATION` a la ubicación del bucket. La ubicación
debe ser compatible con la región de la función (`_REGION`).

Desde este directorio, con `gcloud` autenticado en el proyecto de destino:

```bash
gcloud builds submit --config=codebuild.yml \
  --substitutions=_FUNCTION_NAME=gcp-encryption-cloud-function,_REGION=us-central1,_BUCKET=nombre-del-bucket,_TRIGGER_LOCATION=us-central1
```

La cuenta de servicio de Cloud Build debe tener permisos para desplegar Cloud
Functions Gen 2 y configurar el trigger de Eventarc. La cuenta de servicio del
trigger también necesita permiso para publicar eventos de Cloud Storage.
