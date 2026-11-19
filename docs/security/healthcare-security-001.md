# HEALTHCARE-SECURITY-001

Identidad y autorización de las cinco demostraciones en el laboratorio. No es conformidad sanitaria ni autorización de un despliegue público.

## Arquitectura

El navegador entra a Mini HIS o Mini LIS por HTTPS. Spring Security inicia Authorization Code con PKCE. El ID token abre la sesión web y su audiencia es el cliente. El access token, con audiencia `hospital-ai`, queda en la sesión del servidor y es lo que Mini HIS presenta al AI Service junto con el token de máquina. Un ID token enviado como si fuera un access token se rechaza. Keycloak es el mismo proceso que ya atiende Perú y España. El realm nuevo es `hospital-lab`. El navegador solo tiene la cookie de sesión.

```text
Navegador --cookie--> Mini HIS / Mini LIS --token de servicio + access token hospital-ai--> AI Service
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
- `HOSPITAL_OIDC_ISSUER`, `HOSPITAL_OIDC_AUDIENCE=hospital-ai` y `HOSPITAL_OIDC_JWKS_URI` en el AI Service
- `MINI_HIS_OIDC_ACCEPTANCE=true` y `MINI_LIS_OIDC_ACCEPTANCE=true` para exigir HTTPS en las rutas del navegador

Si el cliente OIDC está apagado, la clave local sigue existiendo y no cuenta como aceptación.

## Sesión

La cookie es `HttpOnly` y `SameSite=Lax`. Dura 30 minutos. `Secure` queda apagado en HTTP de loopback y se enciende con `MINI_HIS_COOKIE_SECURE=true` detrás de `infra/healthcare-security-001/Caddyfile`. El proxy escucha en `127.0.0.1:8445` y `127.0.0.1:8444` porque `8443` ya lo usa otro contenedor local, que no se detuvo. El cierre de sesión invalida la cookie si el CSRF coincide. Un CSRF ausente no cierra la sesión. El ingreso OIDC rota la sesión. Los usuarios sintéticos llevan un correo `usuario@hospital.lab.example` verificado para que Keycloak 26 no detenga el ingreso en el perfil.

Los formularios siguen enviando el campo `csrf`. En el perfil OIDC, Spring Security también lo exige. En el perfil local, la comprobación sigue en el controlador. No se desactiva el CSRF de la aplicación para hacer pasar un formulario.

## Tokens de servicio

`X-Service-Token` autentica a Mini HIS frente al AI Service. `Authorization: Bearer` lleva el access token de audiencia `hospital-ai` y solo lo agrega el servidor. El ID token no se reenvía. El navegador no llama los endpoints internos. Un token de servicio sin access token, o un ID token en su lugar, responde 401 y no hay decisión.

## Auditoría

Mini HIS crea `security_event` si no existe. Mini LIS la agrega con Flyway `V5__security_event.sql`. Los registros de ingreso, salida y denegación no incluyen la clave ni el token. La auditoría clínica de episodios y resultados no se mezcla con esta tabla.

## Pruebas

La matriz negativa de token cubre firma ajena, caducidad, emisor, audiencia, organización ajena y rol que no coincide con la vinculación. Mini HIS cubre anónimo, clave local rechazada, auditor, organización ajena, IDOR de paciente, orden y episodio, CSRF y cierre de sesión. AI Service cubre la decisión con actor falsificado, el hash distinto, la reutilización y la caída del JWKS. Esas pruebas no sustituyen un recorrido de navegador con el realm importado.

## Lo comprobado en el Keycloak en ejecución

`hospital-lab` se creó por la Admin API, sin reiniciar Keycloak y sin tocar el volumen. `platform-001` siguió respondiendo y sus clientes no cambiaron: sigue `lab-review-web`. El access token real de `mini-his-web` trae `typ=Bearer`, `azp=mini-his-web`, audiencia `hospital-ai`, usuario, organización y rol. El ID token trae `typ=ID` y audiencia `mini-his-web`. Un ID token no autoriza al AI Service.

`8445` y `8444` presentan el mismo certificado de hoja, emitido por `Caddy Local Authority - ECC Intermediate` y encadenado a `Caddy Local Authority - 2026 ECC Root`. La huella SHA-256 de la hoja es `1B9C9B2E7D458D2B88637F24DC711BFB15A038646C6380AE619F7FBBEF6BB5D9`. La de la raíz es `D55F1D5A1EFFB117B9BD8BB3DA3652475925DECF80D2C54C861C9FC53C52DA7C`. No se instaló esa raíz en el almacén de Windows. Un Edge anterior usó `--ignore-certificate-errors-spki-list` sobre la hoja: ese ingreso es evidencia funcional, no una validación TLS. El perfil aislado de Firefox importa solo el certificado público de la raíz, con `security.enterprise_roots.enabled` en falso, y abre `https://127.0.0.1:8445/ward/login` comprobando cadena, nombre y vigencia.

`http://127.0.0.1:8095/ward/login` responde 403. En ese Firefox, `medico.his` y `revisor.his` llegan con sesión OIDC. El formulario del portal usa el token de la aplicación. Spring no añade otro CSRF con el mismo nombre, porque ese segundo token rechazaba el POST. Las tarjetas de resumen, intercambio y resultado crítico responden «Disponible». El resumen llega al servicio, pero la federación deja Mini LIS en `identity_unresolved` con el sistema de identificador de Mini HIS, así que el caso no se completa. El 404 visto en el callback de Perú era el proxy de prueba reenviando, en la misma conexión, una petición con URL absoluta que Uvicorn no enruta. La petición directa al contenedor vigente responde 303 hacia el ingreso cuando el método o la cookie no cierran la sesión. Con el proxy corregido, `reviewer-pe` abre `org-pe-lab-demo` y `reviewer-es` abre `org-es-lab-demo`, cada uno en su puerto y con su historial. No se reconstruyó ese perfil ni se modificó el realm `platform-001`.

## Límites

El resultado queda parcial. No hay certificación, no hay exposición pública y una caída de Keycloak no publica ni aprueba: la operación responde denegada o no disponible. El puerto `8443` sigue ocupado por otro contenedor y no se detuvo.
