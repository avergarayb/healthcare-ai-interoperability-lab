# ADR-109 — Catálogo de demostraciones y red interna HL7

## Estado

Aceptado para el laboratorio. No autoriza despliegue remoto ni un proveedor LLM real.

## Decisión

DEMO-CATALOG-001 es un paquete hermano de DEMO-DEPLOY-001. No lo sustituye y no reutiliza sus volúmenes.

DEMO-002 sigue en el Compose de demostración longitudinal. Un nuevo proyecto Compose, `demo-catalog-longitudinal`, puede repetir el caso solo con volúmenes nuevos. Un permiso ya consumido no se reabre.

DEMO-001 y DEMO-003 comparten un Compose interno, `demo-catalog-hospital`, con Mini HIS, Mini LIS, PostgreSQL del LIS y el servicio de integración. Ningún puerto de ese proyecto se publica en el host. El MLLP no sale de la red `demo-catalog-hospital-internal`.

El enlace MLLP acepta un nombre de servicio de un solo componente, como `mini-lis` o `federation`, únicamente cuando el operador activa el permiso de red de contenedor. Sin ese permiso el proceso sigue exigiendo loopback. El permiso no se interpreta como una implementación nacional de HL7.

Cada ejecución hospitalaria usa un identificador de caso nuevo y un permiso durable nuevo, registrado por la API existente. No hay borrado de filas ni de revisiones.

## Consecuencias

La imagen de Mini HIS existe para este paquete. La organización del intercambio sigue siendo `org-mini-his`. El resumen sigue siendo `lab-result-summary-v1`. El componente generativo permanece interceptado.
