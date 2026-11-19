# ADR-112 — Portal local de las cinco demostraciones

## Estado

Aceptado para el laboratorio. No autoriza un agente nuevo, un orquestador ni un proveedor LLM real.

## Decisión

El portal se sirve desde Mini HIS en `/showcase` y reutiliza el sistema visual de la planta. Comprueba la salud de Mini LIS, el intercambio, el AI Service y, si está configurado, el perfil longitudinal. Solo acepta loopback. No muestra secretos y no ejecuta comandos del sistema.

DEMO-001 ejecuta `lab-result-summary-v1` desde `/showcase/demo-001/case`. Mini HIS delega en el AI Service y no entrega el token al navegador. Cada caso abre un permiso nuevo. Con OIDC apagado, la decisión de desarrollo la registra `hl7-reviewer`. La aceptación de HEALTHCARE-SECURITY-001 exige el revisor OIDC y no usa esa identidad. DEMO-002 permanece en su perfil y su OIDC. La sesión de planta no se presenta como esa identidad. Un paso se marca comprobado solo con un hecho leído de la base local o del caso de resumen. La federación y la muestra que este portal no puede leer quedan como verificación externa.

Preparar otro episodio usa la apertura ya existente. No borra historial ni reutiliza un permiso consumido.

## Consecuencias

Las guías de DEMO-001 a DEMO-005 siguen siendo la autoridad de cada recorrido. El portal no las sustituye. No es una certificación ni una conexión con Epic, Oracle o un sistema nacional.
