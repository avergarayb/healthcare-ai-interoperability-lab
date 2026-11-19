# ADR-113 — Identidad OIDC de las demostraciones hospitalarias

## Estado

Aceptado para el laboratorio. No certifica un producto clínico ni autoriza exposición pública.

## Decisión

Mini HIS y Mini LIS aceptan el ingreso web con Authorization Code y PKCE contra el Keycloak que ya existe, en un realm nuevo `hospital-lab`. No se crea otro proveedor ni otro sistema de Human Review. Los realms y clientes de Perú y España no se modifican.

La organización y el rol salen de `infra/healthcare-security-001/bindings.json`. El token firmado tiene que traer el mismo emisor, la audiencia del cliente, la misma organización y el mismo rol. Un formulario, una cabecera o un parámetro no eligen la organización. Un usuario con varios roles no hereda permisos de otra organización: cada aplicación solo acepta los roles de su lista.

Con OIDC encendido, la clave local no abre sesión. Con OIDC apagado, la sesión local sigue disponible para depuración y para las pruebas anteriores, y no es la aceptación. El navegador no recibe el token de servicio ni el ID token en `localStorage`. Mini HIS guarda el ID token en la sesión del servidor y lo reenvía al AI Service junto con el token de servicio. El token de servicio solo identifica a la máquina. La decisión humana exige el ID token y el rol `clinical-reviewer`.

La revisión reutiliza `IamReviewer`, el ledger y la reserva de un solo uso. `hl7-reviewer` permanece únicamente en la ruta de desarrollo.

## Consecuencias

Las cookies de sesión son `HttpOnly` y `SameSite=Lax`. `Secure` se activa con `MINI_HIS_COOKIE_SECURE` o `MINI_LIS_COOKIE_SECURE` detrás del Caddy de loopback. Esta decisión no declara conformidad sanitaria.
