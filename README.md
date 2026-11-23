# encryption-function
Función para cifrado de archivos

## Despliegue con Google Cloud Build

`cloudbuild.yml` actualiza la Cloud Function Gen 2
`gcp-encryption-cloud-function-v2` y configura su trigger de Eventarc para
objetos finalizados en el bucket definido por `_BUCKET`
(`google.cloud.storage.object.v1.finalized`). El entry point es
`handle_storage_event`. Antes del despliegue, `gcloud functions describe`
verifica que la función ya exista en el proyecto y región configurados; si no,
el build se detiene.

Al recibir un objeto nuevo, el handler descarga la generación del objeto,
cifra su contenido con la clave pública `keys/keypair.asc` mediante
`python-gnupg` y sube el resultado al mismo bucket bajo
`encrypted/<nombre-original>.gpg`. Los objetos bajo `encrypted/` se omiten para
evitar que el trigger vuelva a procesar sus propias salidas. El archivo raíz
`Aptfile` instala el ejecutable GPG que necesita `python-gnupg`.

La cuenta de servicio de ejecución de la función requiere permiso para leer
objetos del bucket y crear objetos en él (por ejemplo, los roles
`roles/storage.objectViewer` y `roles/storage.objectCreator`). La clave
incluida es pública; la clave privada correspondiente debe mantenerse fuera
del repositorio y no se necesita para cifrar.

## Pruebas unitarias

Las pruebas mockean el cliente y los blobs de Cloud Storage, y también el
proceso GPG; no acceden a GCP ni cifran archivos reales. Con las dependencias
del proyecto instaladas, ejecútalas desde esta carpeta con:

```bash
python -m unittest discover -s tests -v
```

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

Actualiza `_BUCKET`, `_REGION` y `_TRIGGER_LOCATION` en el YAML para que
coincidan con el bucket y la ubicación del trigger. La cuenta de servicio del
trigger también necesita permiso para publicar eventos de Cloud Storage.
