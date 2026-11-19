# Contrato healthcare-security-001 v1

Ámbito de laboratorio. No es una certificación ni un permiso de despliegue público.

## Identidad

- Emisor previsto: `http://127.0.0.1:18340/realms/hospital-lab` en el Keycloak ya desplegado.
- Clientes públicos con PKCE: `mini-his-web` y `mini-lis-web`.
- Recurso del AI Service: `hospital-ai`. El access token lleva esa audiencia y `typ=Bearer`. El ID token no sirve para esa llamada.
- Redirecciones exactas de aceptación: `https://127.0.0.1:8445/login/oauth2/code/hospital` y `https://127.0.0.1:8444/login/oauth2/code/bench`. `8443` está ocupado por otro proceso local y no se reutiliza.
- La vinculación servidor es `infra/healthcare-security-001/bindings.json`.

## Autorización

| Rol | Organización | Puede |
|---|---|---|
| clinician | org-mini-his | consultar y preparar en Mini HIS |
| clinical-reviewer | org-mini-his | aprobar o rechazar una propuesta ya registrada |
| auditor | org-mini-his | leer |
| operator | org-mini-his | entrar sin mutar clínica |
| receptionist | org-mini-his | registrar y recibir en Mini LIS |
| lab-technician | org-mini-his | procesar y guardar borrador |
| lab-validator | org-mini-his | validar y publicar |

Un rol de otra aplicación o una organización distinta recibe denegación. El auditor no muta. El técnico no publica.

## Decisión humana

`HOSPITAL_OIDC_REQUIRED=true` hace que AI Service ignore el actor publicado y use el ID token. Sin ese token la respuesta es 401 y no hay decisión. Un token de servicio no basta. La segunda decisión de la misma propuesta sigue en `already_decided`. Un hash distinto sigue en `invalid_approval`.

## Auditoría

`security_event` registra actor, rol, organización, acción, recurso, resultado, correlación y fecha. No guarda claves, cookies ni tokens. No sustituye la auditoría clínica.

## Lo que este contrato no hace

No fusiona Perú y España con el hospital. No cambia las máquinas de estados. No abre PostgreSQL ni MLLP. No amplía CORS.
