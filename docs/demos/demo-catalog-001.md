# Catálogo de demostraciones

Guía de ejecución: este archivo. Decisión: [ADR-109](../adr/ADR-109-demo-catalog-001.md). Contrato: [demo-catalog-001-v1](../contracts/demo-catalog-001-v1.md). Fichas: [DEMO-001](demo-001-resumen.md), [DEMO-002](demo-002-longitudinal.md), [DEMO-003](demo-003-hl7.md).

## Cómo ejecutar

Desde `infra/demo-catalog-001`:

```powershell
./run.ps1 prepare
./run.ps1 hospital
```

`prepare` escribe secretos en el directorio temporal del usuario, fuera del repositorio. `hospital` crea un caso nuevo, levanta Mini HIS, Mini LIS, su PostgreSQL y el servicio Java, y ejecuta el intercambio más el resumen. No publica puertos. `hospital-down` detiene los contenedores y conserva los volúmenes. No existe un modo que borre volúmenes.

DEMO-002 se ejecuta con el Compose de [DEMO-DEPLOY-001](demo-deploy-001.md) y un nombre de proyecto nuevo, `demo-catalog-longitudinal`. No se apunta ese comando a `demo-deploy-001` ni a `platform-001`.

## Repetibilidad

Cada llamada a `hospital` sin identificador usa un caso nuevo y un permiso nuevo. El ledger y las revisiones anteriores permanecen. Un permiso consumido no vuelve a enviarse. Si el volumen hospitalario debe conservarse como evidencia, la siguiente presentación usa otro identificador de caso. Un volumen longitudinal ya consumido necesita un proyecto y volúmenes nuevos, no una sentencia SQL.

## Matriz de capacidades

| Capacidad | DEMO-001 | DEMO-002 | DEMO-003 |
| --- | --- | --- | --- |
| Mini HIS / Mini LIS | sí | no | sí |
| HL7 v2.5.1 | después del resultado | no | sí |
| Federación, MCP y LangGraph | sí | sí | sí |
| Gateway interceptado | sí | sí | sí |
| Human Review OIDC | no en este paquete | sí | no en este paquete |
| Revisión durable del mismo componente | sí | sí | sí |

## Evidencia de la verificación final

DEMO-001 y DEMO-003 se ejecutaron dos veces seguidas en Docker Desktop, con identificadores distintos y el proveedor interceptado. El resultado vigente de cada caso cita su observación LIS. Las observaciones anteriores siguen en el expediente, etiquetadas como historia. Detener los contenedores conservó las dos revisiones.

DEMO-002 no se repitió. Sigue READY por la verificación de DEMO-DEPLOY-001. Repetirlo sobre esos volúmenes choca con el permiso ya consumido.

El perfil hospitalario, en reposo, ocupó aproximadamente 647 MiB: Mini HIS 167, Mini LIS 195, federación 240 y PostgreSQL 45. En la misma máquina seguían otros laboratorios. La hipótesis de 8 GB alcanza para un perfil a la vez. No se recomienda sumar el hospital y los dos países cuando además hay otros servicios.

## Límites

No es una plataforma SaaS, no diagnostica, no certifica y no integra Epic ni Oracle en producción. El control de laboratorio no es una certificación regulatoria. La hipótesis de 4 vCPU, 8 GB y 80 GB se mide por perfil. Hospital y los dos países se ejecutan por separado.
