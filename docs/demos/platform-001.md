# Demostración local PLATFORM-001

Entorno sintético para Perú (`pe-lab-demo-v1`) y España (`es-lab-demo-v1`). No es un despliegue público, no es multi-tenancy productivo y no migra SQLite a PostgreSQL.

La fuente clínica de esta demostración es el conector de jurisdicción dentro de Clinical Federation. Mini HIS, Mini LIS y HAPI siguen en su Compose de soporte y no se inician aquí. El realm histórico `lab-review-iam` no se reinicia.

## Qué es real y qué está interceptado

Son reales la federación Java, MCP, LangGraph, el ledger, Human Review y Keycloak. El único transporte simulado es la salida hacia el proveedor del modelo. La política `request_real_provider_send` sigue cerrada, y una clave presente en el entorno no la abre. Al arrancar, cada contenedor elimina su ruta por defecto. Esa eliminación usa `NET_ADMIN` y no es la prueba: `probe.py` tiene que fallar al conectar con el proveedor, y el grafo usa un cliente interceptado.

LangGraph corre dentro de `ai-pe` o `ai-es`. El informe del recorrido trae `executor=linux-container`, `os_name=posix` y `system=Linux`. El ledger de cada perfil está en `/var/lab/ledger` sobre su volumen nombrado. No se usa un bind mount de Windows ni un filesystem de red para esa base. Decisión: [ADR-107](../adr/ADR-107-linux-portable-ledger.md).

## Requisitos

- Docker, con contenedores Linux.
- Puertos locales libres: `18481`, `18482`, `18493`, `18495` y `18340`.
- Para preparar los secretos en Windows, el entorno virtual `services/ai-service/.venv`.

Los secretos se escriben en el directorio de `PLATFORM_RUN_DIR`. Si no está definido, Windows usa `%TEMP%\platform-001\run`. Esa carpeta queda fuera del repositorio. Los scripts no imprimen contraseñas. El recorrido clínico no usa rutas absolutas de Windows: entra con `docker compose exec` al contenedor del perfil.

## Iniciar y detener

Desde la raíz del repositorio:

```powershell
powershell -File infra/platform-001/check.ps1
powershell -File infra/platform-001/up.ps1
powershell -File infra/platform-001/smoke.ps1
powershell -File infra/platform-001/down.ps1
```

`down.ps1` no borra volúmenes. La limpieza de datos sintéticos de este proyecto es aparte y exige confirmación:

```powershell
powershell -File infra/platform-001/clean.ps1 -Confirm
```

Ese comando solo elimina volúmenes cuyo nombre empieza por `platform-001_`. No usa los volúmenes de HAPI, Mini LIS ni del realm histórico.

## Perú o España

No hay un parámetro de petición que elija el país. Cada perfil es un proceso:

| Perfil | Federación | Revisión |
| --- | --- | --- |
| `pe-lab-demo-v1` | `http://127.0.0.1:18481` | `http://127.0.0.1:18493/lab-summaries` |
| `es-lab-demo-v1` | `http://127.0.0.1:18482` | `http://127.0.0.1:18495/lab-summaries` |

El recorrido HTTP, dentro del contenedor:

```powershell
powershell -File infra/platform-001/run-e2e.ps1 -Profile pe-lab-demo-v1
powershell -File infra/platform-001/run-e2e.ps1 -Profile es-lab-demo-v1
```

En un host Linux los mismos pasos son `infra/platform-001/run-e2e.sh pe-lab-demo-v1` y `infra/platform-001/run-e2e.sh es-lab-demo-v1`. Después de un reinicio sin borrar volúmenes, `recover.ps1` o `recover.sh` leen la reserva `consumed`, la reserva `held` y una copia aislada. No vuelven a llamar al modelo.

## Sesión

Keycloak escucha en `http://127.0.0.1:18340`. El issuer es `http://127.0.0.1:18340/realms/platform-001`.

Usuarios: `reviewer-pe`, `auditor-pe`, `reviewer-es` y `reviewer-other`. Las contraseñas están en `user-passwords.json` dentro del directorio de ejecución. No se copian a la documentación ni a Git.

`reviewer-pe` decide casos de `org-pe-lab-demo`. `reviewer-es` decide los de `org-es-lab-demo`. `auditor-pe` no aprueba. `reviewer-other` no abre el caso de otra organización. Una segunda decisión queda rechazada.

En el navegador, abrir la revisión del perfil, pulsar **Continuar al proveedor** e iniciar sesión. El cierre de sesión está en la misma página.

## Pruebas

Las pruebas Python que abren `app/` se ejecutan con el directorio de trabajo `services/ai-service`. Si el temporal de pytest no es escribible, defina `PLATFORM_PYTEST_BASE` a un directorio escribible.

```powershell
powershell -File infra/platform-001/test-python.ps1 tests/test_platform_001.py
```

## Logs y fallos

```powershell
docker compose -f infra/platform-001/compose.yaml ps
docker compose -f infra/platform-001/compose.yaml logs --tail 50 federation-pe ai-pe keycloak
```

Una línea `platform_start` confirma el arranque. `federation_query correlation=` identifica la consulta. Esos registros no incluyen el token ni el cuerpo clínico. Si la revisión responde que la identidad no es aceptable, Keycloak no es alcanzable en el issuer de loopback o el directorio de ejecución cambió. No se desactivan las comprobaciones de issuer, firma o audiencia para corregirlo.

## Copia y restauración

Después de un recorrido:

```powershell
powershell -File infra/platform-001/backup.ps1
```

En Linux, `sh infra/platform-001/backup.sh`. La copia queda en el directorio de ejecución, fuera de Git. La copia interna usa la API de backup de SQLite. Para leerla, el script de recuperación la abre en `/var/lab/restore-isolated`. No la copie sobre el ledger que el proceso está usando ni sobre una base histórica. Detener el proyecto no borra volúmenes.

En la carpeta aislada, abra los archivos solo para lectura. `aip_store.schema_version` debe ser `9`. La revisión conserva el resumen, la fila de evidencia, la decisión y la identidad del revisor. En `aip_remote_execution_reservation` la reserva de esa autorización queda `consumed` y no vuelve a `held`. Una reserva que no está `held` no puede gastarse otra vez.
