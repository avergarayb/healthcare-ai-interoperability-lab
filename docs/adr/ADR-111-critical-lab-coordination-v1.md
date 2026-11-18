# ADR-111 — Coordinación de resultado crítico de laboratorio

## Estado

Aceptado para el laboratorio. No autoriza un proveedor LLM real, un mensaje externo ni un segundo realm.

## Decisión

`critical-lab-coordination-v1` se apoya en el intercambio ya existente y en el mismo servicio de IA del coordinador de alta. No añade otro motor HL7, otra federación, otro Keycloak ni un servidor MCP.

La criticidad sale de la regla de simulación `sim-hemoglobin-low` 1.0 sobre LOINC `718-7` y `g/dL`. El modelo no la decide. El evento queda en Mini LIS aunque el agente no responda.

El banco de Mini LIS separa borrador, validación y publicación. La publicación reutiliza el escritor de resultados y, con eso, el `ORU^R01` que ya existía. Un reintento no inserta otro resultado.

La sesión de `/ward` y `/bench` es local y de loopback. No se presenta como OIDC. La aprobación del agente usa el token de servicio y el hash de la propuesta. La tarea interna nace solo después de esa aprobación.

## Consecuencias

La demostración entra por el navegador en Mini HIS y Mini LIS. El transporte de modelo queda bloqueado salvo `CRITICAL_LAB_MODEL_MODE=intercepted`. Los protocolos son sintéticos, de `org-mini-his`, y vigentes entre 2026 y 2027. Esta decisión no afirma una conexión con Epic, Oracle, un hospital real ni una plataforma nacional.
