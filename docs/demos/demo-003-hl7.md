# DEMO-003 — Integración hospitalaria HL7

**Estado:** READY en la red interna `demo-catalog-hospital` el 18 de noviembre de 2026. No es un conector nacional.

## Problema

Dos sistemas del mismo hospital necesitan una orden y su resultado correlacionados, y después ese resultado puede alimentar un resumen revisable.

## Qué se demuestra

Mini HIS crea la orden. Java envía `OML^O21` por la red interna. Mini LIS responde `ORL^O22`, registra glucosa 90 mg/dL y envía `ORU^R01`. Java confirma y proyecta `ServiceRequest`, `DiagnosticReport` y `Observation`. La organización es `org-mini-his`. El paciente sintético es `MHS-PAT-001`.

Esa proyección es determinista. LangGraph y el resumen pertenecen a DEMO-001 y usan el resultado ya correlacionado. El mensaje HL7 no entra en el texto del modelo. No es una integración productiva, ni un conector de Epic, Oracle, RENHICE o HCDSNS/EHDS, ni una guía nacional de Perú o España.

## Autorización

El MLLP no se publica en el host. Sin el permiso explícito de red de contenedor, el enlace sigue exigiendo loopback. Una organización ajena recibe HTTP 403. Un secreto inválido recibe HTTP 401. Si el LIS está detenido, la sonda no conecta.

## Guion de tres a cinco minutos

El operador lanza el perfil hospitalario. En la salida aparecen el identificador de la orden del HIS, el de la orden del LIS, la observación y la correlación `FED-<caso>`. Esos identificadores son la evidencia. Java mantiene el intercambio dentro de la red de contenedores: el puerto MLLP no se publica. El resumen posterior es DEMO-001 y queda en revisión humana. El mensaje HL7 no entra en el texto que ve el modelo.

## Evidencia

| Caso | Orden HIS | Orden LIS | Observación | Correlación | Referencias |
| --- | --- | --- | --- | --- | --- |
| `catalog-20261118163940938-301993` | `MHS-LAB-963F17691BFA` | `MLS-ORD-FA2E4A521A04` | `MLS-RES-D24B45CEFAB3` | `FED-catalog-20261118163940938-301993` | `basedOn` y `result` apuntan a esa orden y a esa observación |
| `catalog-20261118164030643-766e7d` | `MHS-LAB-1237DFD77841` | `MLS-ORD-A926945A7B15` | `MLS-RES-88E05BA19CBA` | `FED-catalog-20261118164030643-766e7d` | `basedOn` y `result` apuntan a esa orden y a esa observación |

Federación `complete` en ambos. Los puertos 8095, 8096, 2575 y 8081 no quedaron publicados. El perfil en reposo usó unos 635 MiB.

## Límites

El listener no está expuesto a Internet. No hay un motor HL7 nuevo. Si el LIS no responde, la orden no se da por entregada. Un reinicio no borra la correlación ya guardada en el volumen del catálogo.
