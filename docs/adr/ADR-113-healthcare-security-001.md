# ADR-113 — Identidad OIDC de las demostraciones hospitalarias

## Estado

Aceptado para el laboratorio. No certifica un producto clínico ni autoriza exposición pública.

## Decisión

Mini HIS y Mini LIS aceptan el ingreso web con Authorization Code y PKCE contra el Keycloak que ya existe, en un realm nuevo `hospital-lab`. No se crea otro proveedor ni otro sistema de Human Review. Los realms y clientes de Perú y España no se modifican.

La organización y el rol salen de `infra/healthcare-security-001/bindings.json`. El ID token autentica al usuario en Mini HIS o Mini LIS y su audiencia es el cliente web. No autoriza una llamada al AI Service. Esa llamada lleva el access token, con audiencia `hospital-ai`, tipo `Bearer` y `azp` del cliente web, además del token de servicio. El AI Service comprueba firma, emisor, audiencia del recurso, caducidad, sujeto, rol y organización. Un ID token firmado para `mini-his-web` se rechaza.

Con OIDC encendido, la clave local no abre sesión. Con OIDC apagado, la sesión local sigue disponible para depuración y para las pruebas anteriores, y no es la aceptación. El navegador no recibe el token de servicio ni el access token. Mini HIS guarda el access token en la sesión del servidor. La decisión humana exige ese access token y el rol `clinical-reviewer`.

La aceptación web entra por `https://127.0.0.1:8445` y `https://127.0.0.1:8444`. Esas son las únicas redirecciones registradas. El puerto `8443` ya lo ocupa otro contenedor local y no se detuvo. El emisor de Keycloak sigue en el loopback HTTP ya usado por Perú y España; cambiarlo rompería ese realm.

La revisión reutiliza `IamReviewer`, el ledger y la reserva de un solo uso. `hl7-reviewer` permanece únicamente en la ruta de desarrollo.

## Consecuencias

Las cookies de sesión son `HttpOnly` y `SameSite=Lax`. `Secure` se activa con `MINI_HIS_COOKIE_SECURE` o `MINI_LIS_COOKIE_SECURE` detrás del Caddy de loopback. Esta decisión no declara conformidad sanitaria.
