# HEALTHCARE-DEPLOY-001

Paquete privado y reproducible para una VM Ubuntu. Esta ejecución se hizo en Windows con Docker Desktop. No hubo VM Ubuntu ni distribución WSL aparte de `docker-desktop`. Eso deja la validación de VM en **BLOCKED**. No es una certificación clínica ni una exposición pública.

## Arquitectura

```mermaid
flowchart LR
  browser["Navegador en 127.0.0.1"] --> caddy["Caddy"]
  subgraph edge["red edge, publicada"]
    caddy --> keycloak["Keycloak"]
  end
  subgraph hospital["red hospital, interna"]
    caddy --> his["Mini HIS"]
    caddy --> lis["Mini LIS"]
    caddy --> ai["AI Service"]
    his --> exchange["Intercambio FHIR"]
    exchange --> lis
  end
  keycloak --> kdb["PostgreSQL Keycloak"]
  lis --> ldb["PostgreSQL Mini LIS"]
```

Perú y España no comparten esta red. Siguen en `infra/demo-deploy-001`, con redes y volúmenes propios. NeutralModelGateway no es un contenedor: corre dentro del AI Service. HAPI local no entra en este paquete.

## Matriz de servicios

| Servicio | Imagen | Puerto interno | Datos | Publicado |
|---|---|---|---|---|
| Caddy 2.10.2 | `caddy:2.10.2-alpine` | 18543, 18445, 18444, 18490 | volumen de la CA | `127.0.0.1` |
| Keycloak 26.8.1 | imagen fijada por digest | 8080 | PostgreSQL | no |
| PostgreSQL Keycloak | `postgres:16.10-alpine` | 5432 | volumen | no |
| Mini HIS | Java 21, Temurin, jar existente | 8095 HTTP, SQLite | volumen | no |
| Mini LIS | Java 21, Temurin, jar existente | 8096 HTTP, 2575 MLLP | PostgreSQL | no |
| Intercambio FHIR | Java 21, Dockerfile existente | 8081 HTTP, 2576 MLLP | SQLite | no |
| AI Service | Python 3.13 | 8090 | SQLite de ledger y revisión | no |
| PostgreSQL Mini LIS | `postgres:16.10-alpine` | 5432 | volumen | no |

El proxy de emisor es `socat` en Alpine, unido al espacio de red de Mini HIS o Mini LIS. Escucha `127.0.0.1:18543` y entrega el flujo a Caddy. El emisor del token y la URL que valida el servicio son la misma. Caddy ata sus sitios a `127.0.0.1`, porque un cliente que llega por la dirección del puente no completa el handshake del certificado de esa IP. `caddy-edge` reenvía las direcciones IPv4 del contenedor hacia ese loopback. El puerto de host `18443` pertenece a `demo-deploy-001`; este paquete usa `18543`.

Variables de modelo: `CRITICAL_LAB_MODEL_MODE=intercepted` y `DISCHARGE_MODEL_MODE=intercepted`. El entrypoint del AI Service retira `GEMINI_API_KEY` y `OPENAI_API_KEY` si aparecen en el entorno.

## Perfiles

`hospital` y `showcase` arrancan el mismo conjunto. `maintenance` arranca solo las dos bases. `longitudinal` no crea contenedores en este archivo.

No hace falta tener los cinco recorridos encendidos a la vez. El escenario de 4 vCPU y 8 GiB es una hipótesis de planificación, no una capacidad medida de una VM.

## Secretos

`scripts/prepare.sh` escribe archivos de modo `0600` en `run/secrets/`. Compose los monta como secrets. `env.example` solo tiene marcadores. El realm generado sustituye `REPLACE_AT_IMPORT` y los puertos `8445`/`8444` por `18445`/`18444`. No se imprime el valor.

## HTTPS y OIDC

Caddy usa `tls internal`. La consola de administración de Keycloak no está enrutada: cualquier ruta distinta de `/realms/` y `/resources/` responde 404. Las cookies de Mini HIS y Mini LIS piden `Secure`.

La raíz de Caddy se copia a `run/caddy-root.crt` después del primer arranque. Java la importa en un almacén temporal del contenedor. El AI Service la usa como `SSL_CERT_FILE`. No se ejecuta `caddy trust` ni se toca el almacén de Windows.

## Firewall del host

Estas reglas son documentación. No se aplicaron en esta máquina.

```sh
ufw default deny incoming
ufw allow OpenSSH
ufw deny 5432
ufw deny 2575
ufw deny 2576
ufw deny 8081
ufw deny 8090
ufw deny 8095
ufw deny 8096
```

Los puertos HTTPS de Caddy quedan en loopback y no necesitan apertura hacia la red. No cerrar el acceso administrativo SSH de una máquina compartida.

## Persistencia

| Dato | Tratamiento |
|---|---|
| PostgreSQL de Keycloak y Mini LIS | volumen nombrado, imprescindible |
| SQLite de Mini HIS, intercambio y ledger | volumen nombrado, imprescindible |
| Realm y bindings | generados o copiados en `run/`, regenerables desde el repositorio salvo la contraseña |
| Secretos | `run/secrets/`, fuera de Git |
| CA de Caddy | volumen `caddy-data`, regenerable; los clientes deben volver a confiar la raíz nueva |

`scripts/stop.sh` no borra volúmenes. No se usa `docker compose down -v`.

## Respaldo y restauración

`scripts/backup.sh` ejecuta `pg_dump` dentro del contenedor de cada PostgreSQL y la API `Connection.backup` de SQLite sobre el volumen, no una copia del archivo activo. El manifiesto guarda identificador, fecha, tamaño y SHA-256. El permiso de archivo no es cifrado: este paquete no cifra los respaldos.

`scripts/restore-test.sh` hace la restauración en un proyecto Docker distinto. Inserta `case-deploy-001` / `synthetic-order-kept`, restaura en otro volumen y comprueba la fila. Al terminar retira solo esos contenedores, volúmenes y la red del ensayo.

## Rollback

1. Anotar la etiqueta de imagen anterior y la nueva.
2. Ejecutar `backup.sh` y conservar el directorio.
3. Si la migración Flyway ya se aplicó, no hay sentencia inversa en este paquete.
4. Restaurar el volcado en un volumen nuevo, como hace el ensayo.
5. Volver a la etiqueta de imagen anterior solo después de comprobar el marcador.
6. Repetir `health.sh`.

Reconstruir la etiqueta `0.1.0` no deshace una migración.

## Observabilidad

Cada servicio tiene healthcheck. Los logs usan el controlador `json-file`, con rotación de 10 MiB y tres archivos. No se añade Prometheus ni Grafana. Los healthchecks no devuelven historias clínicas ni tokens. `scripts/health.sh` imprime estado y salud.

## Rendimiento

La medición de esta sesión es la del ensayo de restauración y la memoria que Docker Desktop reporta, no un servidor de 8 GiB. Los cinco escenarios simultáneos no se arrancaron. El perfil hospitalario y el longitudinal se operan por separado antes de pedir un servidor mayor.

## Guion de las cinco demostraciones

Con el perfil `hospital` sano, en el navegador de prueba que ya confía la raíz de Caddy:

1. DEMO-001: `https://127.0.0.1:18445`, ingreso OIDC, paciente nuevo, resumen, revisión humana y auditoría.
2. DEMO-002: parar el perfil hospitalario si la memoria no alcanza y arrancar `infra/demo-deploy-001` para Perú y después España.
3. DEMO-003: orden en Mini HIS, entrega HL7 a Mini LIS y resultado FHIR.
4. DEMO-004: resultado crítico, agente con modelo interceptado, aprobación y tarea reconocida.
5. DEMO-005: episodio nuevo, alta preparada y una sola tarea de seguimiento.

Un caso nuevo obtiene un permiso nuevo. Esta sesión no ejecutó esos recorridos.

## Resultados de esta ejecución

Entorno: Windows, Docker Desktop, motor `linux` 29.4.0, 4 CPU y 5.788 GiB visibles para Docker. WSL solo tiene la distribución `docker-desktop`. No se instaló Ubuntu ni se modificó el firewall o el almacén de certificados.

| Área | Resultado |
|---|---|
| Linux VM Ubuntu | BLOCKED |
| WSL Ubuntu | BLOCKED. No está instalada |
| Motor de contenedores | Linux, sobre Docker Desktop. No es una VM Ubuntu |
| Build del proxy de emisor | PASS. Imagen `healthcare-deploy-loopback-proxy:0.1.0` desde Alpine 3.22.1 |
| Builds de Mini HIS, Mini LIS, intercambio y AI | PASS en la continuación |
| Compose y puertos loopback | PASS. `scripts/verify.sh` |
| Red interna de prueba | PASS. El contenedor de la red alcanzó a su vecino y no abrió `1.1.1.1:443` |
| OIDC, HTTPS de navegador y DEMO-001 a DEMO-005 | El perfil llegó a salud real y después el motor dejó de responder. Ver la continuación |
| Backup del ensayo | PASS. 1218 bytes, SHA-256 `4642ccbfb07269f187927890318e13844a8470e62f2db896cdbf75dd22a8239d` |
| Restauración aislada | PASS. 15 segundos. Marcador `synthetic-order-kept` en PostgreSQL y en la copia SQLite |
| Rollback | PASS del ensayo sobre un volumen nuevo. No se revirtió una migración Flyway en un volumen en uso |
| Muestra de recursos | El PostgreSQL restaurado ocupaba 33.84 MiB y 0.04 % de CPU en el instante posterior. No es la carga de una demostración |
| Egress de los servicios clínicos | No observado |
| Cifrado de respaldos | No. Solo quedan fuera de Git |

## Continuación: integración en Docker Desktop

Se construyeron las cuatro imágenes de aplicación y el proxy, todas `linux/amd64`, salida 0. Mini HIS tardó 46 s y pesa 155641870 bytes. Mini LIS tardó 42 s y pesa 147248975 bytes. El intercambio tardó 80 s y pesa 203980689 bytes. AI Service tardó 2 s sobre caché y pesa 84978196 bytes. El proxy tardó 3 s, pesa 4344951 bytes y su usuario es `proxy`. Las imágenes Java y la de AI declaran usuario `root`: es el Dockerfile existente, sin cambio de lógica clínica. Ningún Dockerfile copia `.env` ni secretos.

Antes de arrancar, `docker stats` sumaba unos 4269 MiB de 5927 MiB. El mayor consumidor ajeno era `careflow-local-control-plane`, unos 2,58 GiB. No se detuvo. El perfil `hospital` llegó a healthcheck sano: Keycloak y sus dos PostgreSQL, Mini LIS, intercambio, Mini HIS y AI Service. Caddy estaba sano. Una sonda HTTPS con la raíz de este paquete, sin desactivar la validación, obtuvo 200 en `https://127.0.0.1:18543/realms/hospital-lab/.well-known/openid-configuration` y 404 en `/admin`. Mini HIS respondió 200 en `/ward/login`. Mini LIS en `/bench/orders` redirigió al emisor.

Después el motor dejó de ser alcanzable. El registro de Docker Desktop repite `connect tcp 192.168.65.7:2376: no route to host`. Un ping a esa dirección agotó el tiempo. `vmmemWSL` ocupaba 4161–4336 MiB. El handshake TLS del host hacia los cuatro puertos publicados quedó en `TimeoutError`. No se reinició Docker Desktop: eso habría detenido los proyectos que debían conservarse. No se ejecutaron el navegador, DEMO-001 a DEMO-005, el respaldo de los almacenes reales, la restauración aislada de esos datos, el rollback de este perfil ni el egress de los contenedores clínicos durante un recorrido. El ensayo de 1218 bytes sigue siendo el único restore demostrado. Los respaldos no están cifrados.

La VM Ubuntu independiente sigue **BLOCKED**. No se instaló. El estado de la entrega sigue **PARTIAL**. Para terminar los recorridos hace falta que el motor de 5,8 GiB vuelva a enrutar, con margen además de los proyectos ya residentes. Un fallo de memoria o de ruta del motor no es un defecto de la lógica clínica.

## Continuación: navegador y recorridos

Más tarde la API volvió a responder por `desktop-linux` y `npipe`. `docker-desktop` es la distribución WSL2 interna de Docker Desktop, no una VM Ubuntu. Un `docker info` devolvió error 500 y, veinte segundos después, `docker ps` mostró el perfil `hospital` sano. No se reinició Docker ni se modificó WSL.

La sonda HTTPS con la raíz de este paquete volvió a dar 200 en el descubrimiento, 404 en `/admin`, 200 en el ingreso de Mini HIS, redirección de Mini LIS hacia el emisor y 200 en `/health` del AI Service. Durante los recorridos, los contenedores ocupaban: Caddy 28 MiB, Keycloak 544 MiB, Mini HIS 165 MiB, Mini LIS 194 MiB, intercambio 167 MiB y AI Service 105 MiB.

El navegador de prueba es el Firefox portable ya presente en el perfil aislado. Una política de esa instalación importa la CA pública de este paquete. `security.enterprise_roots.enabled` permanece en falso. No hubo excepción TLS. Las tres páginas —ingreso de Mini HIS, autorización de Mini LIS y realm— abrieron sin aviso de certificado. `medico.his` llegó a `https://127.0.0.1:18445/showcase` con el mismo resultado. El cierre de sesión del emisor dejó la navegación colgada, así que el revisor y el personal de laboratorio no obtuvieron un formulario nuevo.

DEMO-001 no creó un caso `sum-`. DEMO-002 muestra Perú y España en su propio despliegue, sin permisos compartidos; no se escribió en esos perfiles. DEMO-003 creó la orden `MHS-LAB-AAEB569B0DC5` y la página capturada no mostró identificador LIS ni correlación. DEMO-004 creó `MHS-LAB-89A385E3A812`; el banco respondió que la sesión no estaba activa. DEMO-005 no empezó. El respaldo de los almacenes reales y su restauración aislada no se ejecutaron.

Sin sesión, `/internal/agent-context` en `18490` respondió 401. `/lab-summaries` y `/review-cases` respondieron 503 con el aviso de identidad no disponible y sin filas de resumen. `/internal/workflows` respondió 405 a GET.

Las imágenes Java y la de AI siguen en `root`. No tienen un usuario de ejecución y cambiarlo exige reconstruir y volver a crear contenedores. Con el motor intermitente y 31 contenedores de otros proyectos en marcha, ese cambio no se aplicó.

Al cerrar el intento, las peticiones HTTPS del host a `18445` y `18490` agotaron el tiempo. `docker ps` tardó 33 segundos y Caddy seguía marcado sano por su healthcheck interno. No se reinició Docker. La aceptación de Docker Desktop queda distinta de una VM Ubuntu, que sigue **BLOCKED**. El estado sigue **PARTIAL**.

