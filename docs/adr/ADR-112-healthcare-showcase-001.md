# ADR-112 — Portal local de las cinco demostraciones

## Estado

Aceptado para el laboratorio. No autoriza un agente nuevo, un orquestador ni un proveedor LLM real.

## Decisión

El portal se sirve desde Mini HIS en `/showcase` y reutiliza el sistema visual de la planta. Comprueba la salud de Mini LIS, el intercambio, el AI Service y, si está configurado, el perfil longitudinal. Solo acepta loopback. No muestra secretos y no ejecuta comandos del sistema.

DEMO-002 permanece en su perfil y su OIDC. La sesión de planta no se presenta como esa identidad. Un paso del recorrido se marca comprobado solo con un hecho leído de la base local.

Preparar otro episodio usa la apertura ya existente. No borra historial ni reutiliza un permiso consumido.

## Consecuencias

Las guías de DEMO-001 a DEMO-005 siguen siendo la autoridad de cada recorrido. El portal no las sustituye. No es una certificación ni una conexión con Epic, Oracle o un sistema nacional.
