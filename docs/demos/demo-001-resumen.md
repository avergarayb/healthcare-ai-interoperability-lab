# DEMO-001 — Resumen de un resultado de laboratorio

**Estado:** READY en la red interna `demo-catalog-hospital` el 18 de noviembre de 2026. La bandeja OIDC no cierra este caso.

## Problema

Un comité quiere ver, en un mismo expediente, el resultado verificado del HIS y el del LIS antes de que una persona acepte el texto.

## Qué se demuestra

El agente existente `lab-result-summary-v1` resume la observación vigente del HIS y la del LIS para `MHS-PAT-001` en `org-mini-his`. Participan Mini HIS, Mini LIS, la federación Java, MCP, LangGraph, el gateway interceptado y Human Review.

La capa determinista elige el contexto, exige UCUM y deja el resumen en `PENDING_REVIEW`. LangGraph ordena esos pasos. El texto del modelo es una simulación local: el proceso no abre un socket hacia Gemini ni OpenAI. Las observaciones finales anteriores del mismo paciente sintético permanecen en el expediente y se etiquetan como historia. No se presentan como el resultado de la orden vigente.

## Autorización y revisión

Cada caso registra un permiso nuevo, `catalog-summary-<caso>`. El permiso consumido no se reenvía. La decisión la registra `hl7-reviewer`, una identidad de laboratorio del componente de revisión. No es una sesión OIDC y este Compose no publica esa identidad.

## Guion de tres a cinco minutos

El caso empieza con dos observaciones finales del mismo paciente. Java las federá y deja fuera el mensaje HL7. El grafo pide un único resumen y lo deja en revisión pendiente. En pantalla se ve el texto citado y el estado `PENDING_REVIEW`. Una persona aprueba. Un segundo intento de decisión queda rechazado. El número que se muestra es el identificador de la revisión y el del permiso `catalog-summary-<caso>`. El texto del modelo es una simulación local: el proceso no llama a Gemini ni a OpenAI. El cálculo clínico no está en ese texto; la procedencia sí.

## Resultado verificable

Una revisión pendiente, una decisión humana y una auditoría. El resumen cita la observación del HIS y la del LIS. Un permiso consumido no se reenvía.

## Evidencia

Dos casos consecutivos del 18 de noviembre de 2026, sin borrar el volumen.

| Caso | Permiso | Resultado vigente | Historia conservada |
| --- | --- | --- | --- |
| `catalog-20261118163940938-301993` | `catalog-summary-catalog-20261118163940938-301993` | `MHS-RES-001`, `MLS-RES-D24B45CEFAB3` | tres observaciones LIS anteriores |
| `catalog-20261118164030643-766e7d` | `catalog-summary-catalog-20261118164030643-766e7d` | `MHS-RES-001`, `MLS-RES-88E05BA19CBA` | incluye el resultado del caso anterior |

Ambos quedaron en `PENDING_REVIEW`, con decisión `approved`, auditoría `decided/recorded` y segundo intento `already_decided`. Cada reserva quedó `consumed`. Las dos bases de revisión siguieron presentes después de detener los contenedores.

## Límites

No es un diagnóstico. La bandeja OIDC de Perú y España no cierra este caso. La decisión de este paquete usa el revisor de desarrollo del mismo componente de revisión, porque este Compose no publica otra sesión.
