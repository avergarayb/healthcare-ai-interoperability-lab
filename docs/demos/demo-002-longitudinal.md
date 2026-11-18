# DEMO-002 — Comparación longitudinal

**Estado:** READY por la verificación HTTPS de DEMO-DEPLOY-001, fusionada en el PR #149. Este catálogo no repitió esos volúmenes. Una ejecución nueva usa `infra/demo-deploy-001` con el proyecto `demo-catalog-longitudinal` y volúmenes nuevos.

## Problema

Dos servicios de laboratorio, en dos países, quieren mostrar una diferencia entre dos fechas sin mezclar pacientes ni permisos.

## Qué se demuestra

La diferencia la calcula el motor determinista: dos fechas, el mismo LOINC y la unidad UCUM. LangGraph ordena la explicación y la deja pendiente de una persona. El texto posterior es el componente generativo simulado. La guía de arranque es [DEMO-DEPLOY-001](demo-deploy-001.md). `run.ps1 longitudinal` solo indica ese entorno y rechaza los proyectos `demo-deploy-001` y `platform-001`.

## Qué se muestra

Perú: perfil `pe-lab-demo-v1`, paciente `PE-PAT-001`, organización `org-pe-lab-demo`, hemoglobina 12.8 a 13.4 g/dL, diferencia +0.6 g/dL. España: perfil `es-lab-demo-v1`, paciente `ES-PAT-001`, organización `org-es-lab-demo`, glucosa 95 a 90 mg/dL, diferencia -5 mg/dL. La diferencia la calcula el motor determinista. El texto posterior es el componente generativo simulado.

## Guion de tres a cinco minutos

Se abre la bandeja de un país por HTTPS. El operador ejecuta el caso sintético. En pantalla aparecen las dos fechas, el mismo LOINC, la unidad UCUM y la diferencia. Java aporta el contexto normalizado y el aislamiento de la organización. El agente ordena la explicación y la deja pendiente de una persona. El revisor del país aprueba. El auditor y la otra organización no pueden decidir. El segundo intento sobre el mismo permiso queda cerrado.

## Límites

No promete un ahorro ni una certificación. No es el conector HL7. Repetir la presentación exige volúmenes nuevos, no una limpieza de la base.
