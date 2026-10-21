# Clinical Context Intelligence v1

El módulo `clinical_context_intelligence.py` lee un `LONGITUDINAL_CONTEXT_V1` ya construido. No abre Mini HIS, no llama a un modelo y no vuelve a ejecutar `POST_CONSULTATION_RESULT_REVIEW_V1` ni `MISSED_FOLLOW_UP_REVIEW_V1`.

Una relación queda confirmada solo cuando el recurso trae la referencia: observación hacia su consulta, cita hacia la cita que reemplaza, o un resultado preliminar y otro final o corregido que comparten esa consulta. La cercanía de fechas no crea una relación. Si falta la referencia, la fecha o el recurso destino, el análisis lo marca como no demostrado o incompleto. Un reemplazo hacia sí mismo, un ciclo o una emisión anterior al inicio de la consulta queda como conflicto.

El resultado `matched`, `not_matched` o `insufficient` se copia del protocolo cuando el llamador lo entrega. `GET /internal/clinical-context-intelligence?caseId=` devuelve el análisis sin ese resultado. La página de revisión lo muestra junto al historial cuando la dirección incluye `timeline=1`.

La narrativa de cita no realizada puede recibir un resumen acotado. Si el proveedor falla o la salida no es válida, no se guarda texto. Una narrativa ya persistida no se reemplaza.
