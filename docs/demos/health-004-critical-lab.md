# HEALTH-004 — Resultado crítico de laboratorio

Guion de 5 a 8 minutos para una audiencia técnica. Los datos son sintéticos. La integración HL7/FHIR es la del laboratorio, no una conexión productiva.

## Objetivo

Mostrar que una orden nace en el hospital, se procesa en el laboratorio, y que una regla determinista —no un modelo— marca el resultado crítico antes de que una persona apruebe una tarea interna.

## Problema

Un valor crítico puede perderse entre la validación del laboratorio y el reconocimiento del clínico. El modelo no debe decidir qué valor es crítico ni ejecutar la tarea por su cuenta.

## Actores

- Médico: usuario `clinica` en Mini HIS. Sesión local de laboratorio, no OIDC.
- Técnico: usuario `tecnico` en Mini LIS. Sesión local, no OIDC.
- Validador: usuario `validador` en Mini LIS. Solo este rol valida y publica.
- Revisor: el mismo médico aprueba o rechaza la propuesta del agente.

## Recorrido

1. En Mini HIS, abrir al paciente sintético y crear una orden de hemoglobina `718-7` con indicación sintética.
2. El envío usa el intercambio existente. Si el laboratorio no responde, la orden queda como no enviada.
3. En Mini LIS, registrar la muestra, confirmar la recepción e iniciar el procesamiento.
4. Guardar el borrador `6.2 g/dL`. Ese paso no publica el resultado.
5. Validar y después publicar. La publicación usa el escritor HL7 ya existente.
6. Volver a Mini HIS. La regla `sim-hemoglobin-low` 1.0 explica la alerta. Hemoglobina `13.4 g/dL` y glucosa `90 mg/dL` no la activan.
7. Preparar el reconocimiento. El agente lee el evento, cita los cinco protocolos vigentes y propone una tarea. La frase del modelo interceptado no es una autorización.
8. Aprobar. Mini HIS crea una sola tarea. Rechazar no la crea. Una segunda aprobación no la duplica.
9. Registrar el reconocimiento o el escalamiento simulado. No sale ningún correo ni mensaje.

## Qué hace cada pieza

- HL7/FHIR: el conector existente lleva `OML^O21` y devuelve `ORU^R01` cuando la publicación ocurre. La pantalla clínica no muestra el mensaje bruto.
- MCP: las lecturas son herramientas internas del grafo, con el mismo límite de servicio. No se añadió un servidor MCP.
- RAG: cinco protocolos sintéticos de `org-mini-his`, con versión y vigencia. Sin evidencia vigente, el agente se abstiene.
- LangGraph: ordena los pasos y puede reanudar una propuesta pendiente sin otra llamada al modelo.
- Automatización: una tarea interna en Mini HIS, después de la aprobación y ligada al hash.
- Auditoría: estado de la orden, evento, propuesta, decisión y tarea quedan persistidos.

## Limitaciones

Los pacientes, los valores y los protocolos son sintéticos. La regla es de simulación. El texto del modelo en la demostración es interceptado, no un proveedor real. No está verificado en producción ni conectado a Epic, Oracle, un hospital real o una plataforma sanitaria nacional. Las sesiones hospitalarias no son OIDC.
