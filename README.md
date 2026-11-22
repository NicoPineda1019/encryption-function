# encryption-function
Función para cifrado de archivos

## Despliegue con Google Cloud Build

`cloudbuild.yml` despliega la Cloud Function `gcp-encryption-cloud-function`
como función Gen 2 activada por Eventarc cuando se finaliza la creación de un
objeto en Cloud Storage (`google.cloud.storage.object.v1.finalized`). Configura
`handle_storage_event` como entry point. Primero ejecuta `gcloud functions
describe` en el mismo proyecto y región; si la función no existe exactamente
allí, el build falla antes de ejecutar el despliegue. El paso imprime el nombre
completo verificado en los logs.

`gcloud functions deploy` puede crear o actualizar funciones. La validación
previa es la que impide que este pipeline intente crear una función nueva. Si
el paso de validación termina correctamente pero el despliegue devuelve un
conflicto de Cloud Run, confirma en los logs que el build usa esta revisión de
`cloudbuild.yml` y que la función y el servicio Cloud Run en conflicto están en
el mismo proyecto y región. No elimines el servicio Cloud Run sin verificar
primero si es el backend de la función existente.

El proyecto también expone `app` como aplicación WSGI para ejecución directa
con Gunicorn/Cloud Run. Si se usa ese modo, Eventarc puede enviar el CloudEvent
al endpoint `/` o `/events`; `/healthz` responde para comprobaciones de salud.

Las APIs deben estar habilitadas antes del despliegue. El build no intenta
habilitarlas porque la cuenta de servicio de Cloud Build normalmente no tiene
permiso `serviceusage.services.enable`. Un administrador del proyecto puede
habilitarlas una vez con:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  eventarc.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  pubsub.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  --project=project-5c6e77ce-7e83-40b5-a20
```

La cuenta de servicio de Cloud Build aún necesita permisos para desplegar Cloud
Functions Gen 2 y configurar Eventarc. La cuenta de servicio del trigger
también necesita permiso para publicar eventos de Cloud Storage.

Desde este directorio, con `gcloud` autenticado en el proyecto de destino y
`PROJECT_ID` apuntando al proyecto que contiene la función:

```bash
gcloud builds submit --config=cloudbuild.yml
```

Actualiza `_BUCKET` y las regiones en las sustituciones del YAML para que
coincidan con el bucket y el trigger. La cuenta de servicio del trigger
también necesita permiso para publicar eventos de Cloud Storage.
