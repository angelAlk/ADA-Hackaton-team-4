# Modelo

## Objetivo
Estimar la probabilidad relativa de que una transacción termine en una denuncia
confirmada de estafa. La decisión usa `fraud_score × amount_mxn` para expresar
el riesgo en pesos y asignar `allow`, `warn` o `delay`.

## Enfoque
- Método: `GradientBoostingClassifier` con 300 estimadores, profundidad 4,
  `learning_rate=0.05`, submuestreo 0.8 y `random_state=42`.
- Desbalance: peso de positivos calculado exclusivamente sobre entrenamiento.
- Variables: las 18 permitidas por `contrato-de-datos.md`; cada continua lleva
  imputación por mediana entrenada en train y un indicador de ausencia estable.
- Split temporal determinista: train semanas 9–21, validación 22–23 y test
  semanas 24–26. Los IDs y checksums quedan en `artifacts/splits/`.
- Selección: umbrales de riesgo en pesos se optimizan solo en validación. Test
  se abre una sola vez para comparar modelo, P-01–P-05 y baseline MTU.

## Resultado
Las métricas ejecutadas se guardan en `artifacts/model_metadata.json` y
`artifacts/evaluation.json`; PR-AUC es la métrica principal. La tabla
`artifacts/policy_comparison.csv` aplica los mismos costos y coeficientes de
efectividad a las tres políticas.

Ejecución del 2026-09-02:

| Conjunto | PR-AUC | ROC-AUC | Tasa base |
| --- | ---: | ---: | ---: |
| Train (9–21) | 0.1056 | 0.9297 | 0.2201% |
| Validación (22–23) | 0.1005 | 0.8705 | 0.2096% |
| Test (24–26) | 0.4133 | 0.9449 | 0.7863% |

Validación eligió umbrales de MXN 1,000 para advertir y MXN 4,300 para
demorar. El resultado **no está listo para despliegue**: el umbral de
advertencia quedó en el borde de la rejilla, el valor neto de validación fue
MXN -19,922 y en test la advertencia alcanzó 10.66%, por encima del guardrail
de 10%. El valor neto positivo observado en test no se usa para retocar
umbrales porque hacerlo contaminaría el holdout.

En test, para referencia:

| Política | Recall | Pérdida prevenida estimada | Valor neto |
| --- | ---: | ---: | ---: |
| Modelo propuesto | 81.51% | MXN 2,115,898 | MXN 1,916,992 |
| P-01–P-05 | 6.89% | MXN 175,647 | MXN -384,689 |
| Solo MTU | 6.24% | MXN 168,526 | MXN -292,485 |

## Limitaciones

- La etiqueta significa estafa completada, denunciada y confirmada; no observa
  fraude bloqueado que nunca se denunció.
- El score ponderado conserva calidad de ranking, pero no debe interpretarse
  como probabilidad calibrada sin una calibración temporal adicional.
- Los snapshots de cliente son estáticos en los datos sintéticos. En producción
  deben reemplazarse por features point-in-time para evitar fuga futura.
- Los costos `V_HORA`, `C_WARN` y `C_OPS` son provisionales de Producto.
- El cambio de régimen de semanas 24–26 hace que las métricas de test sean una
  prueba de generalización temporal, no una estimación i.i.d.
