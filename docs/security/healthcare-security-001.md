# HEALTHCARE-SECURITY-001

Identidad y autorización de las cinco demostraciones en el laboratorio. No es conformidad sanitaria ni autorización de un despliegue público.

## Arquitectura

El navegador entra a Mini HIS o Mini LIS. Spring Security inicia Authorization Code con PKCE, `state` y el control de sesión del cliente OIDC. Keycloak es el mismo proceso que ya atiende Perú y España. El realm nuevo es `hospital-lab`. El ID token queda en la sesión del servidor. El navegador solo tiene la cookie de sesión.

```text
Navegador --cookie--> Mini HIS / Mini LIS --token de servicio + ID token--> AI Service
                              \--OIDC--> Keycloak realm hospital-lab
AI Service --token de servicio--> Federación clínica
```

Perú y España siguen en el realm `platform-001` y en sus clientes. No están en `bindings.json`, así que no entran al hospital aunque compartan el proceso de Keycloak.

## Matriz

| Rol | Mini HIS | Mini LIS | Decisión |
|---|---|---|---|
| clinician | prepara y consulta | no entra | no decide |
| clinical-reviewer | decide propuestas | no entra | sí, con token |
| auditor | lee | lee | no |
| operator | entra sin mutar | no entra | no |
| receptionist | no entra | registra y recibe | no |
| lab-technician | no entra | procesa y borrador | no |
| lab-validator | no entra | valida y publica | no |

La comprobación está en el servidor. Ocultar un botón no autoriza la operación.

## Organizaciones

`org-mini-his` es la organización hospitalaria. `org-pe-lab-demo` y `org-es-lab-demo` siguen aisladas. La organización se lee de la vinculación y se compara con el claim firmado. Un parámetro de URL no la cambia.

## Keycloak

Archivo: `infra/healthcare-security-001/realm-hospital.json`. La clave de los usuarios sintéticos no está en el archivo: el marcador `REPLACE_AT_IMPORT` se sustituye en un temporal al importar con `scripts/healthcare-security-001/import-realm.ps1`. El script no borra realms ni reinicia el servidor. Hay que pasarle el archivo de la clave de administración; no la imprime.

Variables de aceptación:

- `MINI_HIS_OIDC_ENABLED=true`
- `MINI_HIS_OIDC_CLIENT_ENABLED=true`
- `MINI_HIS_OIDC_ISSUER=http://127.0.0.1:18340/realms/hospital-lab`
- `MINI_LIS_OIDC_ENABLED=true`
- `MINI_LIS_OIDC_CLIENT_ENABLED=true`
- `MINI_LIS_OIDC_ISSUER` con el mismo emisor
- `HOSPITAL_OIDC_REQUIRED=true`
- `HOSPITAL_OIDC_ISSUER`, `HOSPITAL_OIDC_AUDIENCE=mini-his-web` y `HOSPITAL_OIDC_JWKS_URI` en el AI Service

Si el cliente OIDC está apagado, la clave local sigue existiendo y no cuenta como aceptación.

## Sesión

La cookie es `HttpOnly` y `SameSite=Lax`. Dura 30 minutos. `Secure` queda apagado en HTTP de loopback y se enciende con `MINI_HIS_COOKIE_SECURE=true` detrás de `infra/healthcare-security-001/Caddyfile`, que solo escucha en `127.0.0.1:8443` y `127.0.0.1:8444`. El cierre de sesión invalida la cookie si el CSRF coincide. Un CSRF ausente no cierra la sesión. El ingreso OIDC rota la sesión.

Los formularios siguen enviando el campo `csrf`. En el perfil OIDC, Spring Security también lo exige. En el perfil local, la comprobación sigue en el controlador. No se desactiva el CSRF de la aplicación para hacer pasar un formulario.

## Tokens de servicio

`X-Service-Token` autentica a Mini HIS o Mini LIS frente al AI Service. `X-Hospital-Identity` lleva el ID token y solo lo agrega el servidor. El navegador no llama los endpoints internos. Un token de servicio sin ID token, con OIDC exigido, responde 401 y no decide.

## Auditoría

Mini HIS crea `security_event` si no existe. Mini LIS la agrega con Flyway `V5__security_event.sql`. Los registros de ingreso, salida y denegación no incluyen la clave ni el token. La auditoría clínica de episodios y resultados no se mezcla con esta tabla.

## Pruebas

La matriz negativa de token cubre firma ajena, caducidad, emisor, audiencia, organización ajena y rol que no coincide con la vinculación. Mini HIS cubre anónimo, clave local rechazada, auditor, organización ajena, IDOR de paciente, orden y episodio, CSRF y cierre de sesión. AI Service cubre la decisión con actor falsificado, el hash distinto, la reutilización y la caída del JWKS. Esas pruebas no sustituyen un recorrido de navegador con el realm importado.

## Límites

El realm no quedó importado en el Keycloak en ejecución durante esta entrega, así que el recorrido de navegador de las cinco demostraciones con una sesión OIDC real queda pendiente. La sesión local no se usa para declarar ese recorrido como aceptado. No hay certificación, no hay exposición pública y una caída de Keycloak no publica ni aprueba: la operación responde denegada o no disponible.
