# Experiencia visual de la demostración cross-org

Vista de solo lectura sobre los reportes que genera [la demostración operativa](end-to-end-operational-v1.md). No es un sistema clínico validado para producción. No vuelve a evaluar el protocolo, no aprueba casos y no consulta HAPI ni Clinical Read.

La página vive en el AI Service existente. El acceso es el mismo inicio de sesión de desarrollo que Human Review.

## Cómo abrirla

1. Ejecutar `run_demo.py run --keep` si se quiere ver el caso de esa ejecución.
2. Abrir `http://127.0.0.1:18290/review-login` y usar `review-login.secret` de esa ejecución.
3. Abrir `http://127.0.0.1:18290/demo-experience`.

Un reporte histórico se puede abrir aunque Mini HIS, Mini LIS y el exchange ya estén detenidos. Hace falta el proceso de AI Service que lee `services/ai-service/.tmp-e2e-demo`. Si esa variable de entorno `DEMO_EXPERIENCE_REPORT_ROOT` apunta a otro directorio, solo se leen `report.json` y `current.json` dentro de él.

## Qué muestra

- Identificador, momento UTC tomado del identificador, y si el reporte está completo.
- Entorno activo solo cuando `current.json` dice que esa ejecución sigue en marcha. El resto se marca como reporte histórico.
- Los servicios del perfil: Mini HIS, exchange, Mini LIS, Clinical Federation, LangGraph y Human Review.
- La comparación entre el escenario positivo y el negativo con los estados guardados.
- Una línea de tiempo. Una etapa queda sin evidencia cuando el reporte no trae el dato.
- Las referencias y, si el reporte la guardó, la proyección JSON. Esa proyección no es un FHIR Bundle ni el envelope completo.
- El enlace a `/review-cases/{id}` cuando hay un caso. Si no hay caso, la página lo dice.

## Estados

| Estado | Significado |
|---|---|
| completa | El reporte trae la referencia o el estado de esa etapa |
| registrada | El reporte trae la evaluación del protocolo, sin recalcularla |
| otra orden | El resultado final pertenece a otra orden |
| caso abierto | Hay un identificador de caso |
| sin caso | El reporte indica que no se creó revisión |
| sin evidencia | Falta el campo en el reporte |
| entorno activo | `current.json` marca esa ejecución como `running` |
| reporte histórico | La ejecución no está marcada como activa |

## Ejemplo sintético

Ejecución `E2E-20261023T141128Z-7C6DC4`.

Positivo: paciente `MHS-PAT-002`, encuentro `MHS-CON-002`, orden HIS `MHS-LAB-76F17A1F66AC`, correlación `EXC-61A5EFFE3CED4D61`, orden LIS `MLS-ORD-5C98CB86646E`, evaluación `matched`, LangGraph `waiting_human`, caso `136abd43-f26c-4041-883c-894a55847834`.

Negativo: paciente `MHS-PAT-003`, encuentro `MHS-CON-003`, orden HIS `MHS-LAB-B39D877F38FA`, correlación `EXC-3AD49DC804A9416F`, orden LIS `MLS-ORD-E43340700926`, evaluación `not_matched` por `result_order_mismatch`, LangGraph `completed`, sin caso.

## Limitaciones

La consulta finalizada sigue saliendo de la semilla aislada. Un reporte anterior a esta vista puede no traer la proyección JSON; en ese caso se muestran solo las referencias guardadas. El enlace de Human Review aparece solo si el caso existe en esta instancia del AI Service. Si el reporte se abre en otro proceso, la página muestra el identificador y dice que el caso no está aquí. No copia ni restaura el caso. La página no sustituye la revisión humana.
