# Paquete de demostración para una VM

Este paquete prepara una sola VM Ubuntu. No compra infraestructura, no abre un dominio y no despliega en Hetzner. PLATFORM-001 sigue igual. Decisión: [ADR-108](../adr/ADR-108-demo-deploy-001.md).

## Qué entra

Caddy es el único puerto publicado. En la verificación local escucha en `127.0.0.1:18080` y `127.0.0.1:18443`, porque 8080 y 8443 ya estaban ocupados en el equipo de laboratorio. El certificado de prueba cubre `demo.localhost`, `pe.demo.localhost` y `es.demo.localhost`. Ese certificado no es una configuración pública.

Detrás del proxy están Keycloak, su PostgreSQL, y los perfiles `peru` y `spain`. Cada perfil tiene su federación, su AI Service, su ledger y su revisión. No se publican los puertos de Java, Python ni PostgreSQL. `/admin` no se enruta.

El issuer local es `https://demo.localhost:18443/realms/demo-deploy`. La validación de issuer, firma, audiencia y PKCE S256 sigue activa. HTTP solo sigue permitido en `127.0.0.1`.

No hay clave de proveedor. La política de la aplicación sigue cerrando el envío. Este proyecto no concede `NET_ADMIN`.

## Qué no entra

Mini HIS no tiene imagen. La demostración hospitalaria HL7 queda fuera de este Compose. No es un conector nacional. Los volúmenes de HAPI, Mini LIS y `platform-001` no se usan.

El modo VM está en `Caddyfile.vm.example` y no se monta. `preflight.py` lo rechaza mientras `DEMO_VM_AUTHORIZED` no sea `true`.

## Comandos

Definir `DEMO_RUN_DIR` fuera del repositorio. En Windows puede ser un directorio temporal. Luego, desde la raíz:

```sh
sh infra/demo-deploy-001/check-host.sh
sh infra/demo-deploy-001/up.sh
sh infra/demo-deploy-001/backup.sh
sh infra/demo-deploy-001/down.sh
```

`down.sh` no borra volúmenes. `update.sh` guarda el id de imagen, copia el backup y vuelve a construir la etiqueta `0.1.0`. Esa reconstrucción no es un rollback entre versiones.

Un solo país:

```sh
docker compose -f infra/demo-deploy-001/compose.yaml --profile peru up -d
```

## Secretos

`prepare.py` escribe tokens, la contraseña de PostgreSQL, el realm y el certificado de prueba en `DEMO_RUN_DIR`. No imprime esos valores. En Linux exige que esos archivos no sean legibles por el grupo ni por otros.

## Datos que hay que recuperar

Cada país comparte un volumen entre su federación y su AI Service.

| Almacén | Ruta en el volumen | Copia |
| --- | --- | --- |
| Ledger | `/var/lab/ledger/<perfil>/processing.sqlite3` | API de backup SQLite |
| Human Review | `/var/lab/review/lab-summary.sqlite3` | API de backup SQLite |
| Auditoría de federación | `/var/lab/federation-audit/security-audit.sqlite` | API de backup SQLite |
| Sesión IAM | `/var/lab/iam/session.sqlite3` | API de backup SQLite, si el archivo existe |
| Keycloak | base `keycloak` en `demo-keycloak-db` | `pg_dump` |

La evidencia longitudinal, la decisión, la identidad y la organización están dentro de Human Review, no dentro del ledger. El seguimiento y el índice de conocimiento se crean vacíos al arrancar y no forman parte de esta copia. España puede no tener sesión IAM si nadie inició sesión en ese host.

## Copias

`backup.sh` escribe el dump y las copias SQLite en `DEMO_RUN_DIR/backup`. La comprobación lee esas copias y, para PostgreSQL, importa el dump en `keycloak_restore_check` y luego elimina esa base. No sustituye los volúmenes en uso. Un segundo consumo del permiso ya consumido, hecho sobre la copia, se rechaza y la fila sigue en `consumed`.

## Actualización

`update.sh` guarda el id de la imagen `0.1.0` que está en marcha, ejecuta el backup y reconstruye esa misma etiqueta. Reconstruir la misma etiqueta no demuestra un rollback entre versiones. Si hubo una migración, la recuperación es volver a apuntar el id guardado y restaurar la copia.

## Firewall que queda pendiente

Cuando exista la VM, el Product Owner tendrá que limitar SSH a las direcciones que confirme y permitir solo 80 y 443 hacia el proxy. Estos scripts no cambian el firewall ni SSH de la máquina actual. `DEMO_VM_AUTHORIZED` solo permite el modo de configuración público. No cierra la salida de red.

La política de la aplicación rechaza el envío real. El E2E usa transporte interceptado. En Docker Desktop el contenedor AI sí abrió TCP hacia `generativelanguage.googleapis.com:443`. Este paquete no está aislado de proveedores a nivel de red. Borrar la ruta por defecto no se considera protección.

En la activación remota hay que comprobar, desde los contenedores AI y sin cambiar este equipo:

- reglas de egreso compatibles con Docker Engine en Ubuntu;
- denegación hacia endpoints de proveedores no autorizados;
- HTTPS, OIDC y los servicios internos después de aplicar las reglas;
- que las actualizaciones y la emisión del certificado no queden bloqueadas.

## Recursos

La hipótesis de evaluación es 4 vCPU, 8 GB de RAM y unos 80 GB de disco. No es un requisito confirmado. En Docker Desktop, con Perú y España a la vez y después del arranque, el consumo residente medido fue aproximadamente 1,3 GiB. Los techos configurados suman unos 5,1 GiB. El ledger de cada país ocupó cerca de 1 MB, PostgreSQL unos 68 MB y los datos de Keycloak 24 KB. No se tomó una serie de CPU durante el grafo. Con esa medición la hipótesis de 8 GB sigue teniendo margen para el sistema operativo. No se bajó la durabilidad.

El proceso de Caddy vio 4 CPU en el motor local. Eso describe esta máquina, no una VM contratada. Las imágenes medidas fueron AI 399 MB, federación 645 MB, Keycloak 751 MB, PostgreSQL 16.10 394 MB y Caddy 83 MB.

## Checklist para Hetzner

- [ ] Hostname confirmado por el Product Owner. No usar un nombre inventado.
- [ ] DNS del hostname, de `pe` y de `es` apuntando a la VM.
- [ ] Ubuntu x86-64 con Docker Engine y Compose.
- [ ] Puertos 80 y 443 libres. SSH restringido.
- [ ] `DEMO_VM_AUTHORIZED=true` solo después de esa confirmación.
- [ ] Sustituir el certificado de prueba. No reutilizar `demo.localhost`.
- [ ] Backup antes de la primera migración.
- [ ] Smoke HTTPS, discovery, un perfil y la revisión humana.
- [ ] Sin datos reales y sin clave de proveedor.
- [ ] Egreso denegado desde los contenedores AI, con HTTPS, OIDC y actualizaciones todavía posibles.

## Clasificación

`VERIFIED_LOCAL` cubre HTTPS con la CA de prueba, OIDC, las dos comparaciones longitudinales, el backup completo y la restauración aislada. Se ejecutó en Docker Desktop con un cliente HTTP. `PENDING_REMOTE` cubre la VM, el DNS, el certificado público y el firewall de egreso. `PENDING_STACK` cubre Mini HIS y el agente de resumen dentro de este Compose. `RISK_ACCEPTED_FOR_DEMO` cubre el socket de proveedor que sí conectó y el uso de una sola VM con datos sintéticos.

## Demostraciones

La comparación longitudinal de Perú quedó en PASS: `+0.6 g/dL`, organización `org-pe-lab-demo`. La de España quedó en PASS: `-5 mg/dL`, organización `org-es-lab-demo`. El agente de resumen no se verificó en este Compose. El recorrido hospitalario HL7 queda `PENDING_STACK` porque Mini HIS no tiene imagen. La siguiente tarea de catálogo es empaquetar esa demostración hospitalaria y validar el agente de resumen en este entorno. Perú y España están separados por volumen y por organización. Compartir la VM no mezcla esas organizaciones. Los datos siguen siendo sintéticos.
