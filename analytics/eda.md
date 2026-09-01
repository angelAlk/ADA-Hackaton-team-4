# EDA — Análisis Exploratorio de Datos

**Equipo 4 · Frente B — Fraude, alerta y demora** **Reto:** política de MTU para decidir entre permitir, advertir o aplicar una demora **Dataset:** 4 archivos Parquet · \~1M de filas · 120 días de transacciones

---

## 1\. Resumen ejecutivo

| Hallazgo | Evidencia |
| :---- | :---- |
| La política actual captura 4.7% de las estafas | 135 de 2,872 confirmadas |
| El 99.8% de las demoras son falsos positivos | 24,420 de 24,462 |
| Las reglas de demora son **peores que el azar** | Lift 0.62x y 0.41x vs tasa base |
| El MTU no es la señal que discrimina | `mtu_ratio` lift 1.5x vs `device_new_flag` 10.2x |
| Existe un cambio de régimen en semanas 24–27 | 44.5% de las estafas en 4 de \~20 semanas |
| La "pérdida capturada" es pérdida **materializada** | 100% de las estafas confirmadas se completaron |

---

## 2\. Inventario de datos

| Archivo | Filas | Columnas | Grano | Llave |
| :---- | :---- | :---- | :---- | :---- |
| `transactions.parquet` | 901,286 | 14 | Una fila por transacción | `txn_id` |
| `customer_mtu.parquet` | 90,000 | 9 | Una fila por cliente | `customer_id` |
| `policy_events.parquet` | 37,925 | 12 | Una fila por evento de política | `event_id`, FK `txn_id` |
| `scam_reports.parquet` | 4,272 | 6 | Una fila por denuncia | `report_id`, FK `txn_id` |

### Integridad referencial

| Cruce | Resultado | Lectura |
| :---- | :---- | :---- |
| `transactions` ∩ `policy_events` | 37,925 / 37,925 | 100% de los eventos tienen transacción |
| `transactions` ∩ `scam_reports` | 4,272 / 4,272 | 100% de las denuncias tienen transacción |
| `policy_events` ∩ `scam_reports` | 161 | Transacciones con regla disparada Y denuncia |

Sin huérfanos. Los cruces por `txn_id` y `customer_id` son completos.

### Cobertura

- **4.21%** de las transacciones dispararon alguna regla de política (37,925 / 901,286)  
- **0.47%** de las transacciones tienen denuncia asociada (4,272 / 901,286)  
- **2.32%** de las transacciones no se completaron (20,902 / 901,286)

---

## 3\. Esquemas

### `transactions`

| Columna | Tipo | Notas |
| :---- | :---- | :---- |
| `txn_id` | integer | PK |
| `customer_id` | integer | FK a `customer_mtu` |
| `txn_ts` | timestamp\_ntz | Momento de la transacción |
| `amount_mxn` | float | Monto |
| `channel` | string | `spei_out`, `card_online`, `cash_out`, `p2p_nu`, `card_present` |
| `counterparty_id` | integer | Destino — **no explotado, ver §8** |
| `counterparty_first_seen_flag` | boolean | Primera vez que este cliente transfiere a este destino |
| `device_id` | integer | Dispositivo |
| `device_new_flag` | boolean | Dispositivo nuevo para el cliente |
| `geo_state` | string | Estado de la transacción |
| `hour_of_day` | byte | 0–23 |
| `is_weekend` | boolean |  |
| `mtd_volume_before_mxn` | float | Acumulado del mes **antes** de esta transacción |
| `completed_flag` | boolean | Si la transacción se completó |

### `customer_mtu`

| Columna | Tipo | Notas |
| :---- | :---- | :---- |
| `customer_id` | long | PK |
| `tenure_months` | long | Antigüedad de la cuenta |
| `income_band` | string | Banda de ingreso |
| `mtu_declared_mxn` | double | **Techo mensual declarado** — denominador del `mtu_ratio` |
| `mtu_observed_p95_mxn` | double | p95 del comportamiento real |
| `avg_ticket_90d_mxn` | double | Ticket promedio 90 días |
| `prior_scam_report_flag` | boolean | Denuncia previa |
| `risk_segment` | string | `low`, `medium`, `high` |
| `home_state` | string | Estado de residencia |

### `policy_events`

Contiene `rule_id`, `rule_description`, `action_taken` (`delay` / `scam_alert` / `none`), `policy_holdout_flag`, `minutes_blocked`, `ops_contact_flag`, `customer_proceeded`, `bypass_requested`, `bypass_granted`, `mtu_breach_flag`.

> ⚠️ Las últimas cinco son **posteriores a la acción**. Ver §7.

### `scam_reports`

Contiene `confirmed_scam` (boolean), `loss_amount_mxn` (double), `reported_ts` (timestamp), `report_channel` (`app` / `phone` / `chat`).

---

## 4\. La variable objetivo

| `confirmed_scam` | Conteo | Pérdida promedio | Pérdida total |
| :---- | :---- | :---- | :---- |
| `true` | 2,872 | $2,675.38 | $7,683,695.99 |
| `false` | 1,400 | $0.00 | $0.00 |

**Tasa base global: 0.319%** (2,872 / 901,286) — desbalance de **313:1**.

### Distribución de pérdidas

| Estadístico | Valor |
| :---- | :---- |
| Promedio | $2,675.38 |
| p25 | $731.89 |
| Mediana | $1,820.19 |
| p75 | $3,544.78 |
| p95 | $7,804.63 |
| Máximo | $35,175.18 |

| Rango de pérdida | Casos | Pérdida total | % del total |
| :---- | :---- | :---- | :---- |
| $0–500 | 495 | $139,360 | 1.8% |
| $500–1K | 445 | $329,238 | 4.3% |
| $1K–2K | 604 | $899,427 | 11.7% |
| $2K–5K | 891 | $2,828,409 | 36.8% |
| $5K–10K | 358 | $2,362,319 | 30.7% |
| $10K+ | 79 | $1,124,943 | 14.6% |

**El 15.2% de los casos (≥$5K) concentra el 45.3% de las pérdidas.** Esto justifica que la política se diseñe sobre **pérdida esperada** y no sobre probabilidad sola.

### Hallazgo crítico: la pérdida equivale al monto

`avg_amount` de transacciones fraudulentas \= **$2,675.38** `avg_loss` de denuncias confirmadas \= **$2,675.38**

Son idénticos. La pérdida es el monto completo de la transacción, así que:

```
pérdida_esperada = P(estafa | x) × amount_mxn
```

No se requiere un modelo de severidad separado.

### Canal de denuncia

| Canal | Casos | Pérdida promedio |
| :---- | :---- | :---- |
| `app` | 1,641 | $2,678.42 |
| `phone` | 789 | $2,780.69 |
| `chat` | 442 | $2,476.10 |

Sin señal diferencial relevante entre canales.

---

## 5\. Diagnóstico de la política actual

### Por regla

| Regla | Descripción | Disparos | Acción | Estafas | Exposición | Min. bloqueados | Contactos ops |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| P-01 | `mtu_ratio` \> 1.00 | 20,685 | delay | 41 | $300,673 | 11,232,671 | 6,607 |
| P-02 | `mtu_ratio` 0.85–1.00 | 9,802 | scam\_alert | 68 | $335,451 | 0 | 0 |
| P-03 | Txn \> 50% del MTU | 1,320 | scam\_alert | 9 | $168,759 | 0 | 0 |
| P-04 | Contraparte nueva \+ \>30% MTU | 806 | scam\_alert | 10 | $94,161 | 0 | 0 |
| P-05 | Cash out 00h–05h | 5,312 | delay | 7 | $4,829 | 2,862,777 | 1,734 |
| **Total** |  | **37,925** |  | **135** | **$903,873** | **14,095,448** | **8,341** |

### Precisión y lift por regla

Tasa base \= 0.319%

| Regla | Precisión | Lift | Acción |
| :---- | :---- | :---- | :---- |
| P-04 | 1.241% | **3.89x** | advertencia |
| P-02 | 0.694% | 2.18x | advertencia |
| P-03 | 0.682% | 2.14x | advertencia |
| P-01 | 0.198% | **0.62x** | **demora** |
| P-05 | 0.132% | **0.41x** | **demora** |

**La inversión es total:** las tres reglas más precisas solo advierten; las dos peores imponen el bloqueo de 12 horas. P-01 y P-05 tienen lift **menor a 1** — una transacción marcada por ellas es *menos* probable de ser fraude que una tomada al azar.

### Eficiencia en la moneda del North Star

| Regla | Horas bloqueadas | Exposición tocada | MXN por hora bloqueada |
| :---- | :---- | :---- | :---- |
| P-01 | 187,211 | $300,673 | $1.61 |
| P-05 | 47,713 | $4,829 | **$0.10** |
| P-02/03/04 | 0 | $598,371 | — (sin bloqueo) |

P-05 consume el 20% de toda la fricción del sistema para tocar $4,829.

### Costo de fricción total

| Métrica | Valor |
| :---- | :---- |
| Clientes legítimos demorados | 24,420 |
| Clientes legítimos advertidos | 11,062 |
| **Horas de bloqueo a legítimos** | **234,831** (\~26.8 años-cliente) |
| Contactos a operaciones | 8,299 |
| Bypass solicitados / otorgados | 8,299 / 5,912 |
| Clientes que procedieron pese a la advertencia | 8,668 |

### Efectividad real de las acciones

| Acción | Tasa | Efectividad |
| :---- | :---- | :---- |
| Advertencia | 78.5% procede igual | **21.5%** de disuasión |
| Demora | 24.2% obtiene bypass | **75.8%** de retención |
| Duración real del bloqueo | 543 min promedio | **9 horas**, no 12 |

### El contrafactual del holdout

| Grupo | n | Estafas | Tasa |
| :---- | :---- | :---- | :---- |
| Holdout (regla disparó, sin acción) | 2,320 | 12 | 0.517% |
| Tratado | 35,605 | 123 | 0.345% |

Implica \~33% de reducción relativa: **\~61 estafas y \~$410K prevenidos**.

> ⚠️ Con solo 12 eventos el intervalo de confianza al 95% de la tasa del holdout abarca aproximadamente 0.27%–0.91%, lo que **incluye valores por debajo de la tasa tratada**. Es la única estimación causal disponible, pero es direccional, no concluyente.

---

## 6\. Análisis de señales

### Comparación estafa vs. legítima (población completa)

| Feature | Estafa (n=2,872) | Legítima (n=898,414) | Lift |
| :---- | :---- | :---- | :---- |
| `device_new_flag` | 37.9% | 3.7% | **10.2x** |
| `counterparty_first_seen_flag` | 68.0% | 11.4% | **6.0x** |
| `ticket_ratio` | 4.15 | 1.38 | 3.0x |
| `prior_scam_report_flag` | 7.0% | 2.8% | 2.5x |
| `amount_mxn` | $2,675 | $1,527 | 1.8x |
| `mtu_ratio` | 0.291 | 0.194 | 1.5x |
| `hour_of_day` | 14.9 | 13.2 | débil |
| `is_weekend` | 28.1% | 29.2% | ninguna |
| `geo_mismatch` | 5.0% | 6.3% | **ninguna (invertida)** |

**Conclusión:** las señales de novedad conductual (dispositivo y contraparte) discriminan entre 4 y 7 veces mejor que el MTU. `geo_mismatch` se descarta — no aporta señal.

### Precisión de las señales individuales (Bayes)

| Señal | Volumen si dispara sola | Precisión | Lift |
| :---- | :---- | :---- | :---- |
| `device_new_flag` | 34,615 | **3.14%** | 9.9x |
| `counterparty_first_seen_flag` | 104,375 | 1.87% | 5.9x |
| P-04 (mejor regla actual) | 806 | 1.24% | 3.9x |

Un flag booleano crudo de dispositivo nuevo es **2.5x más preciso que la mejor regla de la política actual**, sobre un volumen comparable al de toda la política.

### Distribución de `mtu_ratio`

| Estadístico | Valor |
| :---- | :---- |
| Promedio | 0.194 |
| Mediana | 0.096 |
| p95 | 0.717 |
| **Máximo** | **5.248** |

> El máximo de 5.25 confirma que **el MTU no opera como límite duro** en este dataset. Si el techo bloqueara automáticamente, `mtu_ratio > 1` no debería existir; sin embargo 20,685 transacciones lo rebasan. El MTU funciona como umbral de monitoreo que activa política, no como tope. Premisa documentada.

---

## 7\. Calidad de datos y trampas identificadas

### 7.1 Timestamps en nanosegundos

Los Parquet contienen `TIMESTAMP(NANOS)`, no soportado por Databricks Runtime 11.3+. La lectura directa falla con `Illegal Parquet type: INT64 (TIMESTAMP(NANOS,false))`.

**Solución adoptada:** cargar con pandas y truncar a microsegundos antes de convertir a Spark.

```py
pdf[col] = pdf[col].dt.floor("us")
```

### 7.2 Columnas posteriores a la acción — prohibidas como features

| Columna | Por qué |
| :---- | :---- |
| `customer_proceeded` | Existe solo después de mostrar la advertencia |
| `bypass_requested` / `bypass_granted` | Existen solo después de imponer la demora |
| `ops_contact_flag` | Consecuencia de la acción |
| `minutes_blocked` | Consecuencia de la acción |

**Distinción importante:** estas columnas **no pueden entrar al modelo**, pero **sí deben usarse para calibrar la efectividad de cada acción** (de ahí salen el 21.5% y el 75.8%). Son insumos de la función de costo, no del score.

### 7.3 Población censurada

Las estafas exitosamente prevenidas **nunca se convierten en denuncia**. Por construcción, la etiqueta positiva solo contiene fraudes que ocurrieron y fueron reportados. Consecuencias:

- La clase negativa contiene estafas no reportadas → la precisión medida es un **piso**, no el valor real  
- El éxito de la política es **inobservable** en la etiqueta → el holdout es el único estimador válido

### 7.4 "Pérdida capturada" no es pérdida evitada

Verificación ejecutada:

```
completed_flag | n     | total_loss
true           | 2,872 | 7,683,695.99
```

**El 100% de las estafas confirmadas se completaron.** Los $903,873 de "exposición tocada" son dinero que **se perdió** en transacciones donde la política disparó y falló, no dinero salvado.

> Este resultado es en parte tautológico (para que exista pérdida, el dinero tuvo que salir), pero confirma la interpretación de la columna y obliga a renombrar la métrica.

### 7.5 Nulos

Conteo de nulos en features clave tras los cruces: **0** en `mtu_ratio`, `ticket_ratio`, `mtu_gap_ratio`, `tenure_months`, `prior_scam`, `hour_of_day`.

Aun así, el pipeline implementa **imputación por mediana \+ columna indicadora de faltante** para robustez, en lugar de `na.fill(0)` — rellenar `mtu_ratio` con 0 significaría "consumió 0% de su techo", el valor más seguro posible asignado a un desconocido.

### 7.6 Verificación de fuga temporal

Features de tabla dimensión (`prior_scam_report_flag`, `avg_ticket_90d_mxn`, `mtu_observed_p95_mxn`) podrían ser snapshots calculados al final del periodo, lo que filtraría el futuro.

**Prueba:** tasa de estafa entre clientes con `prior_scam = 1`, por bloque de semanas:

| Bloque | Transacciones | Tasa de estafa |
| :---- | :---- | :---- |
| Semanas 1–12 | 4,696 | 0.0070 |
| Semanas 13–18 | 8,941 | 0.0068 |
| Semanas 19–23 | 7,456 | 0.0080 |

Estable. Sin evidencia de fuga.

**Prueba de control:** modelo entrenado sin `prior_scam` ni `tenure_months` → AUC-ROC 0.9358 vs 0.9458 del completo. La caída es marginal, confirmando que la señal no depende de esas columnas.

---

## 8\. El patrón emergente: semanas 24–27

### Volumen y severidad por semana

| Semana | Denuncias | Pérdida total | Pérdida promedio |
| :---- | :---- | :---- | :---- |
| 9–23 (15 sem) | 1,592 | $3,146,564 | \~$1,977 |
| **24** | 314 | $1,063,553 | **$3,387** |
| **25** | 422 | $1,511,784 | **$3,582** |
| **26** | 425 | $1,560,274 | **$3,671** |
| **27** | 118 | $396,733 | **$3,362** |

**4 de \~20 semanas concentran el 44.5% de las estafas y el 59% de las pérdidas.**

### Firma conductual del brote

| Métrica | Semanas 9–23 | Semanas 24–27 |
| :---- | :---- | :---- |
| Contraparte nueva | \~0.50 | **0.86–0.88** |
| Dispositivo nuevo | \~0.32 | **0.43–0.47** |
| Hora promedio | \~12.3 | **17.3–17.9** |
| Monto promedio | \~$1,900 | **$3,362–$3,671** |

El patrón es **conductual, no volumétrico**: uso casi universal de contrapartes nunca vistas, desplazado a la tarde-noche, al doble del ticket habitual.

### Por qué la política actual es ciega

Las reglas P-01 a P-05 son umbrales **estáticos sobre volumen acumulado**. No tienen componente temporal ni de novedad conductual, así que son estructuralmente incapaces de detectar un cambio de régimen. Sobre estas mismas semanas capturan **6.9%** de las estafas.

### Estafas de alto valor

| Métrica | Valor |
| :---- | :---- |
| Estafas ≥ $5K | 437 |
| Capturadas por la política | 69 (15.8%) |
| **No detectadas** | **368** |
| Pérdida no detectada | $2,760,571 |
| Concentración en canal `app` | 202 casos, $1,503,724 |

### Línea de investigación pendiente

`counterparty_id` **no ha sido explotado**. La hipótesis natural del brote son **cuentas mula compartidas** — múltiples víctimas transfiriendo a las mismas contrapartes. Ninguna de las cinco reglas actuales mira ese campo.

Query propuesto:

```
scamConfirmed
  .join(transactions.select("txn_id", "counterparty_id", "txn_ts"), Seq("txn_id"), "inner")
  .groupBy("counterparty_id")
  .agg(count("*").as("n_scams"), sum("loss_amount_mxn").as("total_loss"))
  .filter($"n_scams" > 1)
  .orderBy($"n_scams".desc)
```

> ⚠️ Cualquier feature de historial de contraparte debe construirse con ventana **estrictamente causal** (solo denuncias disponibles al momento de la transacción). Los `reported_ts` llegan con demora; usarlos sin restricción produce fuga.

---

## 9\. Decisiones de modelado derivadas del EDA

| Decisión | Justificación (sección) |
| :---- | :---- |
| Split **temporal** (semanas ≤23 / ≥24), no aleatorio | §8 — el cambio de régimen haría trivial la detección con split aleatorio |
| Umbrales sobre **pérdida esperada**, no probabilidad | §4 — la pérdida equivale al monto; 45% de pérdidas en 15% de casos |
| Descartar `geo_mismatch` | §6 — sin señal, ligeramente invertida |
| Ponderación de clase 456:1 | §4 — desbalance de 313:1 global, 456:1 en train |
| Excluir columnas post-acción del modelo | §7.2 |
| Usar columnas post-acción para calibrar efectividad | §7.2, §5 |
| Reportar **PR-AUC**, no solo ROC-AUC | §4 — clase minoritaria extrema |
| Guardrail: ninguna zona por debajo de la tasa base | §5 — P-01 y P-05 lo violan hoy |

---

## 10\. Limitaciones conocidas

1. **La etiqueta no es "fraude", es "fraude reportado y confirmado".** El modelo aprende propensión a denunciar mezclada con propensión a ser estafado.  
2. **`tenure_months` es la 3ª feature más importante** — no se ha verificado si es riesgo real o comportamiento de denuncia.  
3. **El score no está calibrado.** La ponderación de clase infla las probabilidades predichas. El ranking es válido (la transformación es monótona), la interpretación en pesos no.  
4. **La estimación causal descansa en 12 eventos.** Intervalo amplio.  
5. **`counterparty_id` sin explotar.** Detección de mulas pendiente.  
6. **Datos sintéticos** con nulos intencionales y posibles fugas declaradas por el reto.

---

*Documento vivo. Última actualización tras ejecución sobre dataset completo (901,286 transacciones).*  
