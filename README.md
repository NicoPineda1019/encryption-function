# encryption-function
Función para cifrado de archivos

## Despliegue con Google Cloud Build

`cloudbuild.yml` despliega la Cloud Function `gcp-encryption-cloud-function`
como función Gen 2 activada por Eventarc cuando se finaliza la creación de un
objeto en Cloud Storage (`google.cloud.storage.object.v1.finalized`). Configura
una instancia mínima para reducir los arranques en frío y despliega
`handle_storage_event` como entry point de la función.

El proyecto también expone `app` como aplicación WSGI para ejecución directa
con Gunicorn/Cloud Run. Si se usa ese modo, Eventarc puede enviar el CloudEvent
al endpoint `/` o `/events`; `/healthz` responde para comprobaciones de salud.

El archivo intenta habilitar las APIs requeridas antes del despliegue. La cuenta
de servicio de Cloud Build debe tener el permiso
`serviceusage.services.enable` (por ejemplo, mediante el rol
`roles/serviceusage.serviceUsageAdmin`), además de permisos para desplegar
Cloud Functions Gen 2 y configurar el trigger de Eventarc. Si la organización
no permite que Cloud Build habilite APIs, un administrador debe habilitarlas
una vez por adelantado.

Desde este directorio, con `gcloud` autenticado en el proyecto de destino:

```bash
gcloud builds submit --config=cloudbuild.yml
```

Actualiza `_BUCKET` y las regiones en las sustituciones del YAML para que
coincidan con el bucket y el trigger. La cuenta de servicio del trigger
también necesita permiso para publicar eventos de Cloud Storage.
