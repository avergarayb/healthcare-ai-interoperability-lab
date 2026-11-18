# ADR-110 — Coordinación sintética de alta hospitalaria

## Estado

Aceptado para el laboratorio. No autoriza un alta autónoma, un proveedor LLM real ni un segundo realm.

## Decisión

`inpatient-discharge-coordinator-v1` prepara un borrador a partir del episodio que Mini HIS persiste. LangGraph ordena la lectura, la recuperación de protocolos sintéticos y una sola llamada de modelo. El transporte predeterminado queda bloqueado.

Mini HIS no incorpora tipos FHIR. La proyección R4 la construye el coordinador desde el chart propietario. No se añade Condition ni MedicationRequest.

La aprobación humana queda atada al hash de la propuesta y a la versión del episodio. No cierra la hospitalización. El cierre es otra acción de una persona autorizada. Las tareas de seguimiento salen solo de la propuesta aprobada y una segunda solicitud devuelve las mismas tareas.

HEALTH-004 no está en `origin/main`. Los protocolos de este agente son un corpus sintético propio, con organización, vigencia y abstención. No se reutiliza un módulo inexistente.

## Consecuencias

La demostración entra por `/ward/login` en Mini HIS. El coordinador escucha solo en loopback y exige el token de servicio ya usado en la frontera del servicio de IA. Un caso nuevo necesita una autorización nueva. Las filas anteriores no se borran.
