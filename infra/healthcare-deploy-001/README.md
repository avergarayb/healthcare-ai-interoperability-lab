# Operación de HEALTHCARE-DEPLOY-001

Paquete privado para una VM Ubuntu con Docker Engine y el plugin Compose. Desde Windows, Git Bash puede invocar los mismos scripts; eso no convierte a Docker Desktop en una VM Ubuntu.

## Preparar

```sh
cd infra/healthcare-deploy-001
export DEPLOY_PROFILE=hospital
sh scripts/prepare.sh
```

`prepare.sh` crea `run/` con secretos hexadecimales y una copia del realm hospitalario. `run/` no se versiona. El comando es idempotente y no rota un secreto que ya existe.

## Arrancar y detener

```sh
sh scripts/start.sh
sh scripts/status.sh
sh scripts/health.sh
sh scripts/logs.sh
sh scripts/stop.sh
```

`stop` detiene contenedores y conserva los volúmenes. No existe un comando de borrado de volúmenes.

Perú y España:

```sh
DEPLOY_PROFILE=longitudinal sh scripts/start.sh
```

Ese perfil no levanta otra copia. Indica el paquete `infra/demo-deploy-001`.

## Comprobaciones locales

```sh
sh scripts/verify.sh
sh scripts/restore-test.sh
```

`verify.sh` renderiza Compose, exige que cada puerto publicado esté en `127.0.0.1` y prueba una red Docker interna desechable. `restore-test.sh` crea un proyecto aparte, inserta un marcador sintético, lo vuelca, lo restaura en otro volumen y retira esos recursos.

## Entrada HTTPS

| Superficie | URL |
|---|---|
| Keycloak, solo realm y recursos | `https://127.0.0.1:18543` |
| Mini HIS | `https://127.0.0.1:18445` |
| Mini LIS | `https://127.0.0.1:18444` |
| AI Service | `https://127.0.0.1:18490` |

El certificado es la autoridad interna de Caddy. El navegador de prueba debe confiarla de forma explícita. No se instala en el almacén del sistema. El puerto `18443` pertenece a `demo-deploy-001`. Caddy escucha en `127.0.0.1` y `caddy-edge` reenvía las direcciones del contenedor para que el puerto publicado complete TLS.

En Docker Desktop la API responde por `npipe` aunque la ejecución directa de `docker-desktop` falle. Un Firefox aislado confió la CA de este paquete sin excepción TLS y `medico.his` abrió el portal. Los recorridos completos y el restore de los almacenes integrados siguen abiertos. La VM Ubuntu sigue bloqueada. El detalle está en `docs/deploy/healthcare-deploy-001.md`.

## Respaldo

Con el perfil hospitalario o de mantenimiento en marcha:

```sh
sh scripts/backup.sh
```

El resultado queda en `run/backup/<fecha>/` con `manifest.txt`, volcados SQL y copias SQLite. No se versiona.

La reversión de una migración no es automática. Se restaura el volcado en un volumen nuevo y se comprueba el marcador antes de sustituir el volumen en uso.
