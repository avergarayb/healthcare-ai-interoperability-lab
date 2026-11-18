# Contrato demo-catalog-001-v1

El catálogo registra tres demostraciones. El estado READY exige una ejecución en el entorno de ese caso. Una prueba de otro entorno no cambia el estado.

| Identificador | Caso | Entorno | Organización |
| --- | --- | --- | --- |
| DEMO-001 | `lab-result-summary-v1` | Red interna hospitalaria | `org-mini-his` |
| DEMO-002 | Comparación longitudinal | Compose HTTPS de DEMO-DEPLOY | `org-pe-lab-demo` y `org-es-lab-demo` |
| DEMO-003 | Orden y resultado HL7 v2.5.1 | Red interna hospitalaria | `org-mini-his` |

La preparación de un caso nuevo crea secretos fuera de Git y un identificador `catalog-<instante>-<token>`. El instante incluye milisegundos y el token evita que dos lanzamientos del mismo minuto compartan caso. El permiso durable es `catalog-summary-<caso>`. Un identificador ya consumido no se reutiliza. `run.ps1` rechaza los proyectos `platform-001` y `demo-deploy-001`. Ningún comando del paquete elimina volúmenes.

El proveedor del resumen es una simulación dentro del proceso. No se envía el mensaje a Gemini ni a OpenAI.
