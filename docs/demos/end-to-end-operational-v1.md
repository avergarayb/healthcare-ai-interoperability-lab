# Demostración operativa de extremo a extremo

Recorrido sintético y reproducible:

Mini HIS → Cross-Organization Exchange → Mini LIS → Clinical Federation → LangGraph → Human Review.

No es un sistema clínico validado para producción. No interpreta valores de laboratorio, no aprueba la revisión humana y no sustituye las evidencias federadas por Clinical Read.

HAPI FHIR Server no forma parte de este recorrido. El valor predeterminado `clinical-read.source=local-hapi` no se modifica.

## Prerrequisitos

- Docker Engine, porque Mini LIS persiste en PostgreSQL. `check` no inicia Docker Desktop.
- JDK 21 y Maven.
- El entorno virtual de AI Service en `services/ai-service/.venv`.
- Puertos libres: 18295, 18296, 18281, 18290 y 15434. No usa 8080, 8081, 8090, 8095 ni 8096.

## Servicios

| Servicio | Dirección | Papel |
|---|---|---|
| PostgreSQL aislado | `127.0.0.1:15434` | Solo la base de Mini LIS de esta demostración |
| Mini LIS | `http://127.0.0.1:18296` | Orden y resultado |
| Mini HIS | `http://127.0.0.1:18295` | Consulta sembrada y orden, en un SQLite temporal |
| FHIR Integration Service | `http://127.0.0.1:18281` | Exchange y Clinical Federation |
| AI Service | `http://127.0.0.1:18290` | LangGraph y Human Review |

El contenedor se llama `e2e-demo-pg`. No es el PostgreSQL de HAPI ni el de Compose.

## Comandos

Desde la raíz del repositorio:

```text
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py check
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py run
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py run --keep
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py stop
```

`run` crea un directorio nuevo en `services/ai-service/.tmp-e2e-demo/`. Ese directorio está ignorado por Git. Contiene el reporte, las bases SQLite aisladas de la ejecución —incluidas las auditorías Python y Java— y el secreto local de acceso. El comando no imprime el secreto. No reutiliza los stores de auditoría predeterminados del usuario.

`run` sin `--keep` detiene los procesos y elimina solo `e2e-demo-pg`. `--keep` deja el entorno cuando la ejecución termina bien. Si el arranque falla, los procesos de esa ejecución se detienen aunque se haya pedido `--keep`. `stop` lee `current.json` y limpia solo esos PID y el contenedor `e2e-demo-pg`. No ejecuta `docker compose down -v` y no toca las bases del entorno habitual.

El reporte de la ejecución queda en `services/ai-service/.tmp-e2e-demo/<executionId>/report.json` y `report.md`. El identificador está en `services/ai-service/.tmp-e2e-demo/current.json`.

## Variables

El runner las asigna solo al proceso de demostración. No edita `.env` ni `application.yml`.

- `AI_CLINICAL_CONTEXT_MODE=federated`
- `AI_FEDERATION_REQUESTING_ORGANIZATION_ID=org-mini-his`
- `AI_FEDERATION_PATIENT_SYSTEM_KEY=mini-his`
- `AI_FEDERATION_PATIENT_IDENTIFIER_SYSTEM=https://lab.local/mini-his/patient`
- `AI_FEDERATION_SOURCES=mini-his,mini-lis`
- `AI_SERVICE_HOST=127.0.0.1`
- `SECURITY_AUDIT_DB_PATH=<directorio de ejecución>/security-audit.sqlite3`
- `federation.security-audit.store-path=<directorio de ejecución>/federation-security-audit.sqlite`
- Tokens de laboratorio del exchange y de la federación, distintos del secreto de Human Review.
- El secreto de acceso queda en `review-login.secret` dentro del directorio de la ejecución.

El modo `single` sigue siendo el predeterminado del servicio cuando esas variables no están definidas.

## Datos sintéticos

Cada ejecución abre un SQLite nuevo de Mini HIS. La semilla de ese archivo aporta las consultas. No se leen ni se modifican las bases del puerto 8095.

| Escenario | Paciente | Encounter | Estado de origen | Resultado esperado |
|---|---|---|---|---|
| Positivo | `MHS-PAT-002` | `MHS-CON-002` | `completed` con cierre | `matched`, `waiting_human`, caso abierto |
| Negativo | `MHS-PAT-003` | `MHS-CON-003` | `completed` con cierre | distinto de `matched`, sin caso |

La orden HIS y la orden LIS se crean en esa ejecución. El identificador de intercambio de la orden LIS es el id de la orden HIS. El escenario negativo registra el resultado final en otra orden del exchange, con un id que incluye el identificador de ejecución. Una ejecución posterior no reutiliza esas órdenes ni el secreto de acceso anterior.

## Ejecución positiva

Paciente sintético `MHS-PAT-002`. La consulta finalizada `MHS-CON-002` sale de la semilla del SQLite aislado. El runner crea la orden en Mini HIS, la envía por el exchange real y registra el resultado final en la orden LIS devuelta.

Se espera:

- Federación `complete`.
- Protocolo `CROSS_ORG_LAB_RESULT_REVIEW_V1`.
- Evaluación `matched`.
- LangGraph `waiting_human` en `await_human`.
- Un caso abierto.

## Ejecución negativa

Paciente sintético `MHS-PAT-003`, consulta `MHS-CON-003`. Hay una orden HIS enviada y un resultado final registrado en otra orden del exchange. El protocolo queda distinto de `matched` y no crea caso de revisión.

## Interpretación

El reporte `report.json` muestra el identificador de ejecución, la correlación del exchange, el paciente, la organización `org-mini-his`, las órdenes, el estado del resultado, la federación, el protocolo, la evaluación, LangGraph, el caso y la procedencia. No incluye tokens ni nombres.

Con `run --keep`, el mismo AI Service publica `http://127.0.0.1:18290/demo-experience` después del inicio de sesión. La guía es [experiencia visual v2](demo-experience-v2.md).

## Human Review

Con `run --keep`, abrir `http://127.0.0.1:18290/review-login`. La clave es el contenido de `review-login.secret` de esa ejecución. El caso positivo debe mostrar:

- Encounter de Mini HIS, origen `mini-his`.
- ServiceRequest de Mini HIS, origen `mini-his`.
- ServiceRequest de Mini LIS, origen `mini-lis`.
- Observation final de Mini LIS, origen `mini-lis`.

La página dice que el modo federado no usa Clinical Read de una sola fuente como evidencia. Cerrar el caso sigue siendo una acción humana. Esta demostración no la ejecuta.

## Reinicio seguro

1. `run_demo.py stop` si el entorno anterior sigue activo.
2. Volver a ejecutar `run`. Cada ejecución usa otro directorio, otro SQLite de Mini HIS y un PostgreSQL recreado solo para `e2e-demo-pg`.
3. Si `current.json` indica que la demostración sigue en marcha, el runner no la pisa.

## Solución de problemas

- `dependencies_missing`: falta Docker, Maven o Java. `check` lo muestra sin iniciar nada.
- `port_in_use`: uno de los puertos aislados está ocupado. No cambiar a 8080, 8081, 8090, 8095 ni 8096.
- `postgres_unavailable`: el motor Docker no aceptó el contenedor. Mini LIS lo necesita. No iniciar HAPI para sustituirlo.
- `service_unavailable`: un proceso no respondió a su health check. El log está en el directorio de la ejecución.
- `correlation_mismatch`: la orden LIS no conserva el id de la orden HIS como `externalRequestId`.
- `demo_already_running`: ejecutar `stop` antes de otra demostración.

## Limitaciones

La consulta finalizada proviene de la semilla sintética del Mini HIS aislado. El runner no escribe en el Mini HIS del puerto 8095. Los protocolos `post_consultation` y `missed_follow_up` no cambian. No hay un proveedor de lenguaje nuevo, ni MPI, ni aprobación automática.
