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

Eventarc entrega al handler eventos del bucket indicado. El handler filtra por
`OBJECT_PREFIX`, configurado como `encrypted/` en `cloudbuild.yml`, y descifra
solo los objetos cuyo nombre comience con ese prefijo. El resultado se guarda
en el mismo bucket bajo `desencrypted/<nombre-original>`. Para cambiar el
prefijo, actualiza `_OBJECT_PREFIX` en el YAML. El archivo raíz `Aptfile`
instala el ejecutable GPG que necesita `python-gnupg`.

La passphrase se lee de la variable de entorno `GPG_PASSPHRASE`; debe
configurarse en el entorno de ejecución de la función. No está escrita en el
código ni en el repositorio. La clave privada sí está presente en
`keys/keypair.asc`; restringe el acceso al repositorio y al bucket según la
política de tu organización.

La cuenta de servicio de ejecución de la función requiere permiso para leer
objetos del bucket y crear objetos en él (por ejemplo, los roles
`roles/storage.objectViewer` y `roles/storage.objectCreator`). El archivo
`keys/keypair.asc` contiene material de clave privada; restringe su acceso y no
lo publiques en repositorios compartidos. Para cifrar se usa su clave pública;
para descifrar se requiere la parte privada.

Al cifrar `ruta/archivo.ext`, la función guarda el objeto cifrado en
`encrypted/ruta/archivo.ext.gpg` y un archivo
`encrypted/ruta/archivo_metadata.json`. El JSON registra, para el original y
el cifrado, la ruta de Cloud Storage, el tamaño en bytes y el checksum SHA-256.
Al descifrar, la función compara el checksum SHA-256 del contenido descifrado
con el registrado para el original. Si no coincide, registra el resultado
inválido y no guarda el archivo descifrado. Los eventos del archivo de
metadatos se omiten.

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
