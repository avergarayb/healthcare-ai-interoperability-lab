# Contrato healthcare-deploy-001-v1

Paquete de una VM Linux privada. No es un despliegue público ni una certificación clínica.

## Incluye

- Mini HIS, Mini LIS, el servicio de intercambio FHIR, el AI Service y Keycloak del realm `hospital-lab`.
- Caddy como única entrada HTTPS publicada, en loopback.
- PostgreSQL de Keycloak y de Mini LIS, SQLite de Mini HIS, del intercambio y del ledger del AI Service.
- Respaldo con `pg_dump` y la API de respaldo de SQLite, y restauración en volúmenes nuevos.
- Modelo en modo `intercepted`.

## No incluye

- Kubernetes, Swarm, Terraform, Ansible o Hetzner.
- Otro agente, otro realm de Perú o España, ni cambios de la lógica clínica.
- NeutralModelGateway como proceso separado: vive dentro del AI Service.
- HAPI local. La lectura clínica de este paquete usa Mini LIS.
- Certificado público ni instalación de una raíz en el almacén del sistema.

## Perfiles

| Perfil | Arranque |
|---|---|
| `hospital` | HIS, LIS, intercambio, AI, Keycloak y Caddy |
| `showcase` | Los mismos servicios. El portal ya está en Mini HIS |
| `maintenance` | Solo las dos bases PostgreSQL |
| `longitudinal` | No crea servicios. Delega en `infra/demo-deploy-001` |

Los perfiles hospitalario y longitudinal se ejecutan por separado.
