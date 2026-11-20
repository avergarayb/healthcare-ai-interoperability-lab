# ADR-114 — Paquete privado de despliegue Linux

## Estado

Aceptado para el laboratorio. No certifica un sistema clínico, no autoriza exposición pública y no contrata infraestructura.

## Decisión

1. `infra/healthcare-deploy-001` es un proyecto Compose nuevo. No reemplaza PLATFORM-001 ni DEMO-DEPLOY-001 y no monta sus volúmenes ni el de `local-hapi`.
2. La entrada publicada es Caddy, solo en `127.0.0.1`. PostgreSQL y MLLP no se publican. Las redes de aplicación y de bases son internas y están separadas.
3. El emisor OIDC del navegador y el de los contenedores es `https://127.0.0.1:18543/realms/hospital-lab`. El puerto `18443` queda en `demo-deploy-001` y este paquete no lo publica. Caddy escucha solo en `127.0.0.1`; otro `socat` reenvía las direcciones del contenedor hacia ese loopback para que el puerto publicado y los demás contenedores completen TLS con el certificado de `127.0.0.1`. Un proxy TCP dentro del espacio de red de Mini HIS y Mini LIS reenvía ese puerto a Caddy. No se desactiva la comprobación de emisor, audiencia ni TLS.
4. Perú y España no se duplican. El perfil `longitudinal` sigue delegado en `infra/demo-deploy-001`.
5. Los secretos se generan en `run/`, fuera de Git. El realm importado es una copia del realm hospitalario con los puertos de este paquete. No se modifica el realm `platform-001`.
6. El modelo permanece en `intercepted`. Una migración de base no se revierte en el sitio: la recuperación es restaurar un respaldo en un volumen nuevo.
7. Una VM Ubuntu independiente no forma parte de esta decisión. Docker Desktop no la sustituye.

## Consecuencias

El paquete puede prepararse y comprobarse desde Windows. La aceptación de una demostración privada sobre una VM Linux sigue pendiente hasta ejecutar allí el mismo paquete. El almacén de confianza del host no se modifica.

## Referencias

- [healthcare-deploy-001-v1](../contracts/healthcare-deploy-001-v1.md)
- [healthcare-deploy-001](../deploy/healthcare-deploy-001.md)
- [ADR-108](ADR-108-demo-deploy-001.md)
- [ADR-113](ADR-113-healthcare-security-001.md)
