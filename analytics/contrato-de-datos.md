# Contrato de Datos

**Equipo 4 · Frente B — Política de MTU**

Este documento define **qué se pasa entre las tres áreas, con qué nombres, qué significa cada cosa y qué está prohibido**. Su propósito es que Producto, BA e Ingeniería reporten los mismos números y que nadie tenga que adivinar el significado de una columna.

**Regla de oro:** si un número aparece en el pitch, en el dashboard o en un documento, su definición está aquí. Si no está aquí, no se reporta.

---

## 1\. Partes y responsabilidades

| Área | Responsables | Produce | Consume |
| :---- | :---- | :---- | :---- |
| **Ingeniería** | Marco Polo Aguilar, Ricardo Ruelas, Angel Alcántara | Tablas `master` y `model_data`, pipeline de ingesta | Especificación de features (BA) |
| **Business Analyst** | Ricardo Alfredo Montes, Luis Antonio Domínguez, Francisco Bosch | Score, métricas, umbrales candidatos | `model_data` (Ing.), parámetros de negocio (Prod.) |
| **Producto** | Denisse Dix Cedeño | Parámetros de costo, decisión final de umbrales | Métricas y trade-offs (BA) |

---

## 2\. Fuentes de verdad

Ubicación canónica: `/Volumes/usr/<usuario>/<carpeta>/`

| Archivo | Filas esperadas | Grano | Llave primaria |
| :---- | :---- | :---- | :---- |
| `transactions.parquet` | 901,286 | Transacción | `txn_id` |
| `customer_mtu.parquet` | 90,000 | Cliente | `customer_id` |
| `policy_events.parquet` | 37,925 | Evento de política | `event_id` |
| `scam_reports.parquet` | 4,272 | Denuncia | `report_id` |

**Llaves de cruce:** `txn_id` (transacción ↔ política ↔ denuncia), `customer_id` (transacción ↔ cliente).

### 2.1 Contrato de carga (obligatorio)

Los Parquet contienen `TIMESTAMP(NANOS)`, incompatible con Databricks Runtime 11.3+. **Toda carga debe pasar por el truncado a microsegundos**:

```py
pdf = pd.read_parquet(path)
for col in pdf.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
    pdf[col] = pdf[col].dt.floor("us")
sdf = spark.createDataFrame(pdf)
```

Cargar con `spark.read.parquet()` directamente **falla**. No es opcional.

### 2.2 Validaciones de ingesta

Ingeniería garantiza, antes de entregar `master`:

- [ ] Los cuatro conteos de filas coinciden con la tabla de §2  
- [ ] 100% de `policy_events.txn_id` existe en `transactions`  
- [ ] 100% de `scam_reports.txn_id` existe en `transactions`  
- [ ] `txn_id` es único en `transactions`; `customer_id` es único en `customer_mtu`  
- [ ] Los cruces no duplican filas (`master` debe tener exactamente 901,286 filas)

---

## 3\. Entregable de Ingeniería → BA: tabla `master`

**Grano:** una fila por transacción. **Filas:** 901,286. Construcción: `transactions` ⟕ `customer_mtu` ⟕ `policy_events` ⟕ `scam_reports`.

### 3.1 Features derivadas — definiciones normativas

Estas fórmulas son **la única definición válida**. Si un número no cuadra entre áreas, se revisa contra esta tabla.

| Feature | Fórmula | Interpretación |
| :---- | :---- | :---- |
| `mtu_ratio` | `(mtd_volume_before_mxn + amount_mxn) / mtu_declared_mxn` | Fracción del techo mensual que consumiría **si se autoriza** esta transacción |
| `ticket_ratio` | `amount_mxn / avg_ticket_90d_mxn` | Cuántas veces el ticket habitual del cliente |
| `mtu_gap_ratio` | `mtu_declared_mxn / mtu_observed_p95_mxn` | Qué tan inflado está el techo declarado vs. comportamiento real |
| `is_scam` | `coalesce(confirmed_scam, false)` | Etiqueta objetivo |

**Convenciones:**

- Todo denominador se protege con `when(denominador > 0, ...)`; si es cero o nulo, el resultado es `null`, **nunca 0**.  
- `mtu_ratio` incluye la transacción actual **a propósito** — la decisión es previa a autorizar, se evalúa el estado posterior.  
- Los nulos se imputan en la capa de modelado (mediana \+ indicador), **no** en la construcción de `master`.

### 3.2 Reconstrucción del acumulado mensual

`mtd_volume_before_mxn` viene dado en el Parquet pero **debe validarse** reconstruyéndolo. Especificación:

```
val w = Window
  .partitionBy($"customer_id", year($"txn_ts"), month($"txn_ts"))  // reinicia cada mes calendario
  .orderBy($"txn_ts")                                              // respeta el orden temporal
  .rowsBetween(Window.unboundedPreceding, -1)                      // EXCLUYE la fila actual
```

Los tres elementos son obligatorios. Usar la ventana por defecto incluiría la fila actual e inflaría el ratio.

**Punto abierto:** no está resuelto si las transacciones con `completed_flag = false` deben sumar al acumulado. Correr ambas variantes y adoptar la que reproduzca la columna original. Documentar en `decision-log.md`.

---

## 4\. Entregable de Ingeniería → BA: tabla `model_data`

**Grano:** una fila por transacción. **Uso:** entrenamiento y evaluación del score.

### 4.1 Features permitidas (18)

**Continuas (6)** — imputación por mediana \+ columna `<nombre>_missing`:

| Feature | Origen |
| :---- | :---- |
| `amount_mxn` | `transactions` |
| `mtu_ratio` | Derivada §3.1 |
| `ticket_ratio` | Derivada §3.1 |
| `mtu_gap_ratio` | Derivada §3.1 |
| `hour_of_day` | `transactions` |
| `tenure_months` | `customer_mtu` |

**Binarias (12)** — nulos se rellenan con 0 (ausencia de bandera):

| Grupo | Features |
| :---- | :---- |
| Novedad conductual | `new_counterparty`, `new_device` |
| Contexto | `geo_mismatch_flag`, `is_weekend_flag`, `prior_scam` |
| Canal (one-hot) | `ch_spei_out`, `ch_card_online`, `ch_cash_out`, `ch_p2p_nu`, `ch_card_present` |
| Segmento | `risk_high`, `risk_medium` |

### 4.2 Columnas de acarreo (NO son features)

Necesarias para evaluar políticas, prohibidas como entrada al modelo:

| Columna | Para qué |
| :---- | :---- |
| `txn_id` | Trazabilidad |
| `txn_ts`, `txn_week` | Split temporal |
| `label` | Objetivo |
| `loss_amount_mxn` | Cálculo de pérdida en la evaluación |
| `completed` | Contexto |
| `channel`, `mtu_declared_mxn`, `mtd_volume_before_mxn` | Réplica de la política actual como baseline |

> ⚠️ `loss_amount_mxn` está en la tabla pero **no en `feature_cols`**. Incluirla sería fuga directa del objetivo.

### 4.3 Columnas PROHIBIDAS como features

Son **posteriores a la acción**. Usarlas como entrada del score es fuga de información y descalifica el trabajo:

| Columna | Por qué |
| :---- | :---- |
| `customer_proceeded` | Solo existe después de mostrar la advertencia |
| `bypass_requested` | Solo existe después de imponer la demora |
| `bypass_granted` | Íd. |
| `ops_contact_flag` | Consecuencia de la acción |
| `minutes_blocked` | Consecuencia de la acción |
| `action_taken`, `rule_id` | Decisión de la política vigente |

**Excepción explícita y única:** estas columnas **sí se usan** para calibrar los coeficientes de efectividad de §6. Alimentan la **función de costo**, jamás el **modelo**. La distinción debe quedar escrita en `decision-log.md`.

### 4.4 Feature descartada

`geo_mismatch_flag` se conserva en el esquema pero **se documenta como sin señal**: 5.0% en estafas vs 6.3% en legítimas (ligeramente invertida). Su exclusión del set final es defendible y demuestra selección con evidencia.

---

## 5\. Contrato de partición: split temporal

**Obligatorio para todo entrenamiento y evaluación.** Nadie usa split aleatorio.

| Conjunto | Criterio | Filas | Estafas | Tasa base |
| :---- | :---- | :---- | :---- | :---- |
| Entrenamiento | `txn_week <= 23` | 742,446 | 1,623 | **0.219%** |
| Prueba | `txn_week >= 24` | 158,840 | 1,249 | **0.786%** |

**Razón:** las semanas 24–27 concentran el 44.5% de las estafas (cambio de régimen). Un split aleatorio filtraría el futuro al entrenamiento y haría trivial "detectar" el patrón emergente.

> ⚠️ **La tasa base del test (0.786%) NO es la global (0.319%).** Todo cálculo de lift o guardrail evaluado sobre el test debe usar `y_test.mean()`. Usar la global infla los lifts 2.5x y oculta que las reglas de demora actuales están por debajo del azar.

---

## 6\. Parámetros compartidos

### 6.1 Derivados de datos — propiedad de BA

Calculados de `policy_events`. No se modifican sin recalcular.

| Parámetro | Valor | Origen |
| :---- | :---- | :---- |
| `E_DELAY` | 0.758 | 1 − tasa de `bypass_granted` |
| `E_WARN` | 0.215 | 1 − tasa de `customer_proceeded` |
| `HRS` | 9.0 | Media observada de `minutes_blocked` (543 min) |
| `P_OPS` | 0.34 | Tasa de `ops_contact_flag` dado delay |
| `BASE_RATE` | `y_test.mean()` | **Calculado, nunca hardcodeado** |

> `HRS = 9.0`, no 12\. El bloqueo nominal es de 12 horas pero el promedio real es menor porque los bypasses lo interrumpen.

### 6.2 Juicios de negocio — propiedad de Producto

Estos **no salen de los datos**. Producto los fija y los defiende.

| Parámetro | Valor provisional | Estado |
| :---- | :---- | :---- |
| `V_HORA` | 10.0 MXN | ⏳ Pendiente de confirmación |
| `C_WARN` | 2.0 MXN | ⏳ Pendiente de confirmación |
| `C_OPS` | 50.0 MXN | ⏳ Pendiente de confirmación |

**Referencia para calibrar `V_HORA`:** la política actual entrega $3.76 de pérdida evitada por hora de bloqueo a un cliente legítimo. Si el negocio valora una hora por encima de esa cifra, la política vigente destruye valor neto.

**Restricción sobre `C_WARN`:** debe ser estrictamente positivo. Con costo cero, el optimizador degenera a advertir a toda la población — comprobado experimentalmente (llegó a cubrir el 88% de las transacciones).

---

## 7\. Diccionario de métricas

**Fuente única de verdad.** Cualquier cifra reportada usa estas definiciones exactas.

### 7.1 Nomenclatura de pérdidas — crítica

| Término | Definición | Qué NO es |
| :---- | :---- | :---- |
| `loss_exposure_*` | Suma de `loss_amount_mxn` en transacciones donde la política actuó | **No** es dinero salvado |
| `loss_prevented_est` | `E_DELAY × exposición_demorada + E_WARN × exposición_advertida` | Estimación, no medición |
| `loss_through` | Pérdida en transacciones que se permitieron |  |

> **Por qué importa:** el 100% de las estafas confirmadas tienen `completed_flag = true`. La "exposición" es dinero **que se perdió**, no que se evitó. Confundir ambos infla el desempeño de la política actual en 2.2x. Prohibido usar "captured", "saved" o "capturado" para referirse a exposición.

### 7.2 Métricas de desempeño

| Métrica | Fórmula |
| :---- | :---- |
| `recall` | (estafas demoradas \+ advertidas) / estafas totales |
| `recall_eff` | `(E_DELAY × demoradas + E_WARN × advertidas) / totales` |
| `prec_delay` | estafas demoradas / total demoradas |
| `prec_warn` | estafas advertidas / total advertidas |
| `lift_*` | `prec_* / BASE_RATE` — usando la tasa base **del conjunto evaluado** |
| `PR-AUC` | Métrica principal del modelo (no ROC-AUC — clase minoritaria extrema) |

### 7.3 Métricas de fricción y valor

| Métrica | Fórmula | Unidad |
| :---- | :---- | :---- |
| `legit_delayed` | Clientes legítimos demorados | personas |
| `legit_hours_blocked` | `legit_delayed × HRS` | **horas** (nunca con símbolo $) |
| `costo` | `legit_delayed × (HRS × V_HORA + P_OPS × C_OPS) + legit_warned × C_WARN` | MXN |
| `valor_neto` | `loss_prevented_est − costo` | MXN |
| **North Star** | `loss_prevented_est / legit_hours_blocked` | **MXN por hora bloqueada** |

> **El North Star es métrica de reporte, NO función objetivo.** Optimizar un ratio permite mejorarlo encogiendo el denominador, lo que degenera en advertir a todos y no bloquear a nadie. La optimización se hace sobre `valor_neto`.

---

## 8\. Contrato de la política

### 8.1 Regla de decisión

```
riesgo_en_pesos = fraud_score × amount_mxn

riesgo < UMBRAL_WARN                    → permitir
UMBRAL_WARN ≤ riesgo < UMBRAL_DELAY     → advertir
riesgo ≥ UMBRAL_DELAY                   → demorar
```

**Valores vigentes:** `UMBRAL_WARN = 925 MXN`, `UMBRAL_DELAY = 2,300 MXN`.

**Propiedad garantizada:** como `fraud_score ≤ 1`, ninguna transacción menor a $2,300 puede ser demorada, y ninguna menor a $925 puede ser advertida. El piso es estructural, no depende de la calidad del modelo.

> ⚠️ `fraud_score` **no está calibrado** (la ponderación de clase infla las probabilidades). El ranking es válido; la lectura de "pérdida esperada en pesos" es aproximada. Ver `decision-log.md`.

### 8.2 Guardrails no negociables

Toda configuración propuesta debe cumplir:

1. **Ninguna zona activa por debajo de la tasa base** del conjunto evaluado  
2. **La zona de advertencia no supera el 10%** de las transacciones  
3. **El óptimo no queda en el borde de la rejilla** de búsqueda  
4. **Las horas de bloqueo a legítimos** se reportan siempre; si suben respecto a la política actual, se declara explícitamente como intercambio cuantificado

### 8.3 Comparación obligatoria

Toda propuesta se evalúa contra **dos** referencias, sobre **las mismas filas de test** y con **los mismos coeficientes de efectividad**:

1. Política actual (réplica de P-01 a P-05)  
2. Baseline solo-MTU (demora si `mtu_ratio ≥ 1`, advertencia si ≥ 0.85)

**Validación de la réplica:** las reglas reconstruidas disparan en 4.9% de las transacciones de test vs 4.2% observado en `policy_events`. Coincidencia aceptable.

---

## 9\. Handoffs

| \# | De → A | Entregable | Criterio de aceptación |
| :---- | :---- | :---- | :---- |
| 1 | Ing → BA | `master` (901,286 filas) | Validaciones §2.2 pasan |
| 2 | BA → Ing | Especificación de features §4.1 | Fórmulas de §3.1 implementadas |
| 3 | Ing → BA | `model_data` con `txn_ts` y `txn_week` | Sin `na.fill(0)`; columnas prohibidas ausentes de `feature_cols` |
| 4 | BA → Prod | Métricas §7 \+ tabla comparativa §8.3 | Nomenclatura de §7.1 respetada |
| 5 | Prod → BA | `V_HORA`, `C_WARN`, `C_OPS` | Valores justificados por escrito |
| 6 | BA → Prod | Umbrales óptimos \+ variante de fricción congelada | Guardrails §8.2 verificados |
| 7 | Todos → repo | Documentación en `/docs` y `/analytics` | Números consistentes entre notebook y markdown |

---

## 10\. Reglas de reproducibilidad

1. **Semillas fijas.** `random_state=42` en todo componente estocástico.  
2. **Sin números escritos a mano en código.** Toda cifra se calcula de variables. Prohibido `caughtScams.toDouble / 4`.  
3. **Los resúmenes en markdown se actualizan tras cada re-ejecución.** Un resumen que contradice la celda de arriba es peor que no tener resumen.  
4. **Toda suposición se documenta en `decision-log.md`**, especialmente: MTU como límite mensual declarado, pérdida \= monto de la transacción, y la exclusión de columnas post-acción.  
5. **Los cambios a este contrato se registran en §11.**

---

## 11\. Bitácora de cambios

| Fecha | Cambio | Motivo |
| :---- | :---- | :---- |
| Día 1 | Versión inicial | — |
| Día 1 | Carga vía pandas con truncado a µs | `TIMESTAMP(NANOS)` incompatible con Spark |
| Día 2 | Split aleatorio → temporal | Cambio de régimen en semanas 24–27 |
| Día 2 | `BASE_RATE` hardcodeado → `y_test.mean()` | Ocultaba que las reglas de demora están bajo el azar |
| Día 2 | Umbrales sobre probabilidad → sobre pérdida esperada | La decisión debe escalar con el monto en riesgo |
| Día 2 | Objetivo de ratio → valor neto | El ratio degeneraba a advertir al 88% de la población |
| Día 2 | Nomenclatura `captured` → `exposure` / `prevented_est` | La exposición es pérdida materializada, no evitada |

---

## 12\. Puntos abiertos

| \# | Pregunta | Responsable |
| :---- | :---- | :---- |
| 1 | ¿Cuánto vale una hora de bloqueo a un cliente legítimo? | Producto |
| 2 | ¿Las transacciones no completadas suman al acumulado mensual? | Ingeniería |
| 3 | ¿`tenure_months` mide riesgo o propensión a denunciar? | BA |
| 4 | ¿Bloquear en brecha de MTU es obligación regulatoria (Art. 287 Bis) o discrecional? | Producto |
| 5 | ¿Existen contrapartes que concentran múltiples víctimas (cuentas mula)? | BA |
| 6 | ¿Calibrar el score con isotónica mejora el valor neto? | BA |

