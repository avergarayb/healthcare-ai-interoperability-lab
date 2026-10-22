# Mini HIS longitudinal v2

Mini HIS sigue siendo el simulador sintético. Java Clinical Read conserva el contrato `clinical-read-v1` y el origen `mini-his`. Python lee ese contrato y no abre la base de Mini HIS.

## Datos

Los pacientes `MHS-PAT-001` a `MHS-PAT-006` y los identificadores `SYN-FOLLOWUP-013`, `014` y `015` se conservan. Los pacientes `MHS-PAT-007` a `MHS-PAT-015` agregan citas, consultas y resultados sintéticos, con identificadores `SYN-FOLLOWUP-016` a `024`.

Una fila nueva se inserta solo si su identificador no existe. Las filas ya guardadas no se reescriben. La migración de una base ya existente reconstruye las tablas en una sola conexión y dentro de una transacción, con las claves foráneas apagadas solo durante ese cambio.

## Correspondencias

| Mini HIS | FHIR R4 |
|---|---|
| consulta `completed` | Encounter `finished` |
| consulta `in_progress` | Encounter `in-progress` |
| consulta `scheduled` | Encounter `planned` |
| consulta `cancelled` | Encounter `cancelled` |
| resultado `final`, `preliminary`, `corrected` | Observation con el mismo estado |
| cita `not_attended` | Appointment `noshow` |
| cita `confirmed` | Appointment `booked` |
| cita `scheduled` | Appointment `pending` |
| cita `completed` | Appointment `fulfilled` |
| cita `cancelled` | Appointment `cancelled` |

Si la consulta terminada trae `endedAt` nulo, el Encounter no recibe `period.end`. Si el campo no viene, se mantiene la copia anterior del instante de la visita. Una cita sin `start` se entrega sin fecha. `replacesAppointmentId` se copia a la extensión `https://lab.local/mini-his/StructureDefinition/replaces-appointment`.

`GET /patients/{id}/events` registra el alta sintética y el reemplazo de cita. No es una historia clínica hospitalaria.

## Lectura y protocolos

Java ordena encuentros, observaciones y citas por su instante y deja al final los que no tienen fecha. La procedencia sigue en `meta.source`.

Python arma `LONGITUDINAL_CONTEXT_V1` solo con Clinical Read. El contexto limita la cantidad de recursos y señala fechas o procedencia ausentes. No decide si un protocolo se cumple.

Las reglas `POST_CONSULTATION_RESULT_REVIEW_V1` y `MISSED_FOLLOW_UP_REVIEW_V1` no cambian. Un resultado `corrected` o `preliminary` no sustituye a un resultado `final`. Una cita `cancelled` no abre el protocolo de cita no realizada. La repetición de una petición coincidente reutiliza el caso de revisión.

`GET /internal/longitudinal-context?caseId=` devuelve el contexto. La página de revisión existente lo muestra si la dirección incluye `timeline=1`.
