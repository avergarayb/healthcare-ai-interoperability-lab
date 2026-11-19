# Portal de demostraciones clínicas

El portal vive en Mini HIS, en `http://127.0.0.1:8095/showcase`. No añade un agente, un orquestador ni un despliegue. Las cinco demostraciones siguen en sus guías.

## Arquitectura

Mini HIS pinta las tarjetas y comprueba salud solo en loopback. Un destino que no es loopback queda como no disponible. La página no muestra tokens ni el cuerpo de esas comprobaciones.

| Demostración | Dónde se recorre | Dependencias para decir Disponible |
| --- | --- | --- |
| DEMO-001 Resumen | Ficha de `MHS-PAT-001` y el perfil de catálogo | Intercambio y AI Service |
| DEMO-002 Longitudinal | Perfil aislado Perú/España | Solo si responde su propia salud local |
| DEMO-003 HL7/FHIR | Órdenes de Mini HIS y banco de Mini LIS | Mini LIS e intercambio |
| DEMO-004 Resultado crítico | Mini HIS, Mini LIS y el agente ya existente | Mini LIS, intercambio y AI Service |
| DEMO-005 Alta | Episodios de Mini HIS | AI Service |

Si falta una dependencia, la tarjeta dice «No disponible». DEMO-002 dice «Perfil aislado» hasta que su perfil responda. La sesión de Mini HIS no es OIDC.

## Mapa

1. Portal `/showcase`.
2. Cada tarjeta abre `/showcase/demo-00N`.
3. Los pasos enlazan a `/ward/patients/MHS-PAT-001`, `/ward/orders/new`, `/ward/episodes` o al banco de Mini LIS cuando su salud responde.
4. Un paso dice «Comprobado» solo si la base local tiene la orden, la correlación, el resultado, la propuesta, la tarea, el episodio o la documentación que ese paso nombra.
5. Perú y España no se marcan comprobados desde esta base.

## Preparación del entorno

Requisitos: Java 21, Maven, Python del AI Service y Docker solo para los perfiles que ya lo usan. No hace falta Kubernetes ni un servidor en Hetzner.

Puertos de la presentación local, todos en `127.0.0.1`:

- Mini HIS `8095`, portal incluido. `18095` no es otro puerto del producto: solo se usó cuando `8095` ya estaba ocupado.
- Mini LIS `8096`.
- Intercambio `8081`. El conector de laboratorio, cuando la presentación usa HL7, es `hl7v2` como en el catálogo.
- AI Service `8090`.

Esas direcciones se pueden sustituir con `SHOWCASE_LIS_HEALTH`, `SHOWCASE_FHIR_HEALTH`, `SHOWCASE_AI_HEALTH`, `SHOWCASE_LONGITUDINAL_HEALTH` y `SHOWCASE_LIS_BENCH`. Solo se aceptan URLs de loopback.

La clave de la sesión de planta y los tokens de servicio salen del entorno. No se versionan. Usuarios de la sesión local: `clinica` opera y `auditor` consulta. No son OIDC.

Perfiles:

- Hospital sin puertos publicados: `infra/demo-catalog-001/run.ps1 prepare` y después `hospital`. `hospital-down` detiene y conserva volúmenes.
- Longitudinal: `infra/demo-catalog-001/run.ps1 longitudinal` indica `infra/demo-deploy-001` con el proyecto `demo-catalog-longitudinal`. No usa los proyectos `demo-deploy-001` ni `platform-001`.
- Alta y resultado crítico en el navegador: Mini HIS, Mini LIS, el intercambio y el AI Service en loopback, con el transporte interceptado.

Comprobación: abrir `/showcase`. Las tarjetas deben coincidir con los procesos que realmente responden.

Inicio: arrancar los procesos o el perfil elegido antes de la reunión. Durante el recorrido no hay comandos.

Detención: `hospital-down` o `infra/demo-deploy-001/down.sh` según el perfil. No borran volúmenes. No hay un botón del portal que ejecute el sistema operativo.

## Guion

Unos ocho minutos para las cinco tarjetas, o una sola demostración si la audiencia quiere profundidad.

1. Resumen. El problema es reunir dos resultados. La ficha muestra al paciente. El texto del agente sale del perfil de catálogo, con un permiso nuevo, y una persona lo acepta.
2. Longitudinal. Perú y España siguen separados. La diferencia la calcula el motor. La identidad es el OIDC de ese perfil.
3. HL7. La orden nace en Mini HIS. La correlación es la evidencia. El mensaje bruto no se muestra como ficha clínica.
4. Crítico. La orden, la muestra, la publicación y la regla `sim-hemoglobin-low` 1.0. Luego el agente y la aprobación de una tarea.
5. Alta. Un episodio nuevo no borra el anterior. El borrador cita protocolos. Aprobar no cierra la hospitalización.

## Casos repetidos

En la ficha de alta, «Preparar episodio» llama a la apertura ya existente y genera otro identificador. No reutiliza una autorización consumida y no borra episodios. El resumen del catálogo sigue creando un permiso nuevo por ejecución de `hospital`.

## Límites

No es un producto hospitalario certificado. No hay conexión productiva con Epic, Oracle ni una plataforma nacional. El modelo de estas demostraciones permanece interceptado. El portal no concede un rol que atraviese los cinco casos.

## Diagnóstico

- Tarjeta «No disponible»: el proceso de esa fila no respondió en loopback.
- «Perfil aislado»: DEMO-002 no tiene una salud HTTP en loopback que responda 2xx. El proxy longitudinal publicado redirige a HTTPS con un nombre de laboratorio; esa comprobación no sigue redirecciones ni acepta su certificado de prueba. La revisión OIDC de Perú y España se abre en su propio perfil, no desde Mini HIS.
- Orden «No enviada»: el intercambio no aceptó el envío. El protocolo tiene que ser `hl7v2` cuando la presentación usa HL7.
- El auditor no puede preparar un episodio.

## Evidencia de esta entrega

La prueba del portal comprueba las cinco tarjetas, el perfil aislado, el rechazo de una URL ajena, dos episodios consecutivos y el rechazo del auditor.

La aceptación en navegador, sobre `127.0.0.1:8095`, recorrió el alta, el intercambio y el resultado crítico con los procesos locales. DEMO-004 elige la orden con alerta o reconocimiento cuando hay varias. DEMO-001 abre la ficha y no lanza `lab-result-summary-v1`: ese agente sigue en el perfil de catálogo, con un permiso nuevo por ejecución. DEMO-002 se comprobó en el perfil ya levantado de plataforma, con OIDC de Perú y de España, sin leer esos datos desde Mini HIS y sin repetir un permiso consumido. El portal sigue diciendo «Perfil aislado» mientras su salud HTTP local no responda.
