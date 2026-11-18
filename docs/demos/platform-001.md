# Demostración local PLATFORM-001

Entorno sintético para Perú (`pe-lab-demo-v1`) y España (`es-lab-demo-v1`). No es un despliegue público, no es multi-tenancy productivo y no migra SQLite a PostgreSQL.

La fuente clínica de esta demostración es el conector de jurisdicción dentro de Clinical Federation. Mini HIS, Mini LIS y HAPI siguen en su Compose de soporte y no se inician aquí. El realm histórico `lab-review-iam` no se reinicia.

## Qué es real y qué está interceptado

Son reales la federación Java, MCP, LangGraph, el ledger, Human Review y Keycloak. El único transporte simulado es la salida hacia el proveedor del modelo. Al arrancar, cada contenedor elimina su ruta por defecto: puede hablar con los otros contenedores, pero no con Internet. Esa eliminación usa `NET_ADMIN`. Un proceso del contenedor podría volver a crear la ruta; es un riesgo de laboratorio, no un control de producción.

El recorrido no ocurre entero dentro de Docker. El ledger durable rechaza cualquier sistema que no sea Windows, así que LangGraph se ejecuta en el host y llama al puerto publicado de la federación. `probe.py`, dentro del contenedor, comprueba el HTTP entre servicios y que el socket al proveedor falla. Adaptar el ledger para ejecutar el grafo en un contenedor Linux queda para un incremento posterior. Este no lo resuelve.

## Requisitos

- Docker Desktop en ejecución.
- El entorno virtual `services/ai-service/.venv`.
- Puertos locales libres: `18481`, `18482`, `18493`, `18495` y `18340`. Los puertos `18281` y `18295` quedan libres porque otro proceso del laboratorio ya puede usarlos.

Los secretos se escriben en `%TEMP%\platform-001\run`, o en `PLATFORM_RUN_DIR` si se define. Esa carpeta debe quedar fuera del repositorio. El script no imprime contraseñas.

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

El recorrido HTTP:

```powershell
powershell -File infra/platform-001/run-e2e.ps1 -Profile pe-lab-demo-v1
powershell -File infra/platform-001/run-e2e.ps1 -Profile es-lab-demo-v1
```

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

La copia queda en el directorio de ejecución, fuera de Git. Para recuperarla, copie el SQLite del ledger y el de la revisión a una carpeta nueva. No los copie sobre los archivos que el proceso está usando ni sobre una base histórica, y no use `docker compose down -v`.

En la carpeta aislada, abra los archivos solo para lectura. `aip_store.schema_version` debe ser `9`. La revisión conserva el resumen, la fila de evidencia, la decisión y la identidad del revisor. En `aip_remote_execution_reservation` la reserva de esa autorización queda `consumed` y no vuelve a `held`. Una reserva que no está `held` no puede gastarse otra vez.
