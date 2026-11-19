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

`http://127.0.0.1:8095/ward/login` responde 403. En ese Firefox, `medico.his` y `revisor.his` llegan con sesión OIDC. El formulario del portal usa el token de la aplicación. Spring no añade otro CSRF con el mismo nombre, porque ese segundo token rechazaba el POST. Las tarjetas de resumen, intercambio y resultado crítico responden «Disponible». El 404 visto en el callback de Perú era el proxy de prueba reenviando, en la misma conexión, una petición con URL absoluta que Uvicorn no enruta. La petición directa al contenedor vigente responde 303 hacia el ingreso cuando el método o la cookie no cierran la sesión. Con el proxy corregido, `reviewer-pe` abre `org-pe-lab-demo` y `reviewer-es` abre `org-es-lab-demo`, cada uno en su puerto y con su historial. No se reconstruyó ese perfil ni se modificó el realm `platform-001`.

## Correlación de paciente

Mini HIS usa el sistema `https://lab.local/mini-his/patient` y el valor del identificador local. Mini LIS guarda la terna organización, sistema emisor y valor. Esa terna es la clave única. El mismo valor con otro sistema es otro paciente. No hay correspondencia por nombre.

La federación de una fuente que no es la del llamador solo resuelve `exchange_patient_link`. El intercambio escribe esa fila al aceptar una orden: sistema y valor del emisor, y el identificador lógico del destino. Sin una orden aceptada no hay fila, el resultado es `identity_unresolved` y Mini LIS no se consulta. Dos coincidencias no eligen un paciente y no escriben enlace. Un paciente resuelto sin recursos clínicos es `complete` con `resourceCount` 0; eso no es una identidad ausente.

HL7 lleva el valor en `PID-3-1` y la autoridad asignadora en `PID-3-4`: la organización en `PID-3-4-1`, el sistema en `PID-3-4-2` y el tipo `URI` en `PID-3-4-3`. `PID-3-10` sigue siendo la agencia o el departamento y no identifica al paciente. Sin sistema, una fila se reutiliza solo si ya estaba guardada con el sistema de la organización del laboratorio. Una única fila de otro emisor no se vincula. Un paciente nuevo sin sistema queda en el sistema de la organización del laboratorio, no en un sistema ajeno.

`V6__patient_identifier_system.sql` añade la columna. Las filas de semilla que ya existían recibieron el sistema de su organización.

## Recorridos comprobados

En el Firefox que confía en la raíz de Caddy:

- DEMO-001. `medico.his` creó `sum-8208bbddca3e`. El vigente separó Mini HIS `MHS-RES-001` (13.4 g/dL) y Mini LIS `MLS-RES-3F94369ED382` (11 g/dL). No había otra observación histórica de la misma fuente. `revisor.his` aprobó con identidad OIDC. Repetir el permiso respondió que ya se consumió.
- DEMO-002. Se conserva el ingreso de `reviewer-pe` en `org-pe-lab-demo` y de `reviewer-es` en `org-es-lab-demo`. Este cambio no modifica esos emisores ni esos permisos.
- DEMO-003. `medico.his` envió `MHS-LAB-DD06790DC96F`, correlación `EXC-AFF6977DEFC54585`. Recepción, técnico y validador de Mini LIS publicaron 12.6 g/dL por OIDC. Mini HIS leyó ese resultado.
- DEMO-004. `MHS-LAB-41D6A345FDC1` publicó 6.2 g/dL y la regla `sim-hemoglobin-low` marcó el crítico. Con Mini LIS alcanzable, la propuesta interceptada quedó pendiente. `revisor.his` aprobó y `medico.his` reconoció la tarea. Una preparación anterior, sin la dirección de Mini LIS, respondió que el agente no estaba y dejó el evento crítico en su sitio.
- DEMO-005. El episodio `ENC-D6A8E5B716FC` sigue abierto. La preparación llegó a revisión, `revisor.his` decidió y quedó una tarea de seguimiento. La segunda ejecución no insertó otra.

Mini LIS en `https://127.0.0.1:8444` admite por OIDC a recepcionista, técnico, validador y auditor. La recepcionista no valida ni publica, el técnico no publica y el auditor no modifica. Un CSRF inválido no cambia la orden.

El AI Service lee Mini LIS con `MINI_LIS_BASE_URL` y Mini HIS con `MINI_HIS_BASE_URL`. Cada lectura lleva su `X-Service-Token`. Esos valores no se escriben aquí. Si faltan, la operación queda no disponible y el dato clínico no se borra.

## Límites

Los cinco recorridos del laboratorio quedaron comprobados con identidades OIDC y con la correlación HIS/LIS. Esto no es una certificación ni un despliegue público. Una caída de Keycloak no publica ni aprueba. La hoja local de Caddy vence el 2026-11-20 02:27:38Z; la confianza del perfil está en la raíz. El puerto `8443` sigue ocupado por otro contenedor y no se detuvo.
