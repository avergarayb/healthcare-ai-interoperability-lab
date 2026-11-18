# Alta hospitalaria sintética

Demostración de laboratorio de `inpatient-discharge-coordinator-v1`. El paciente, las notas, las alergias y la medicación son sintéticos. El texto del modelo, cuando el transporte está en `intercepted`, es un borrador local. No es una decisión médica.

## Qué se muestra

Una persona entra a Mini HIS, abre una hospitalización, registra el contexto y pide una preparación. La ficha usa pestañas, estados en español y el borrador en texto, con los protocolos citados y su fragmento. No muestra el JSON de la propuesta. Una tarea de planta abierta deja la preparación incompleta. Después de resolverla, una preparación nueva puede quedar completa. Aprobar el borrador no cierra el episodio. Las tareas de seguimiento se crean una sola vez. El cierre, si se usa, es un botón distinto, en la auditoría.

## Operación local

Definir en el entorno, sin versionarlas, la clave de la sesión, el token de servicio y `DISCHARGE_MODEL_MODE=intercepted`. Mini HIS y el servicio de IA quedan en `127.0.0.1`. La URL del coordinador tiene que ser loopback. Cada clic de preparación genera una autorización nueva. No borrar la base ni las revisiones para repetir el caso.

Usuarios de la sesión: `clinica` puede operar; `auditor` solo consulta. La organización es `org-mini-his`. Esas cuentas son una credencial de laboratorio local. No son OIDC ni un segundo realm de Keycloak. Mini HIS queda en `127.0.0.1` mientras `mini-his.allow-container-bind` esté en falso. El coordinador rechaza una URL que no sea loopback.

## Guion

1. Entrar como profesional autorizado y abrir el paciente sintético `MHS-PAT-001`.
2. Abrir la hospitalización y registrar una nota, una alergia, una medicación documentada y un resultado ya existente.
3. Registrar una tarea pendiente y solicitar la preparación. El checklist queda incompleto y el borrador lo dice.
4. Resolver la tarea, solicitar otra preparación y revisar las citas.
5. Aprobar. El episodio sigue abierto.
6. Crear las tareas de seguimiento y comprobar que un segundo intento no las duplica.
7. Mostrar la auditoría. El cierre, si hace falta, es una acción aparte.

## Pasada en navegador

El 18 de noviembre de 2026, en loopback, una sesión de clínico abrió el episodio sintético `ENC-6D551E662BF3` para `MHS-PAT-001`. Con la tarea de planta abierta, el borrador quedó `checklistComplete` falso y citó la tarea, los cinco protocolos vigentes y los tipos FHIR del chart. Tras resolverla, una preparación nueva quedó completa, sin cerrar el episodio. La aprobación dejó el estado `open` y la documentación `accepted`. Dos solicitudes de seguimiento crearon una sola tarea. El transporte fue el borrador local interceptado.

Esa pasada habilita la demostración local. No es un alta hospitalaria ni una certificación.

La misma tarde, la ficha se recorrió de nuevo con la interfaz de pestañas. El episodio sintético `ENC-243DB3DBB74A` quedó abierto, con la documentación aceptada y una sola tarea de seguimiento. La preparación incompleta citó la tarea de planta. Tras resolverla, el borrador nuevo citó los protocolos vigentes y la aprobación no cerró el episodio. Un segundo seguimiento no duplicó la tarea. El auditor no vio las acciones de escritura.

## Límite

No es un alta de un hospital real, no usa un proveedor LLM en esta pasada y no sustituye la bandeja OIDC de Perú y España. El 18 de noviembre de 2026 la fecha del equipo estaba dentro de la vigencia 2026–2027 y la recuperación devolvió los cinco protocolos. Fuera de esa ventana la preparación se detiene con `protocols_unavailable`, sin guardar un borrador ni inventar citas. El estado READY de esta guía depende de una pasada completa en el navegador, no de las pruebas de API.
