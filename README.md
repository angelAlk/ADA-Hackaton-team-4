# ADA Hackathon — Team 4

## Objetivo
Construir una solución basada en datos para el desafío de políticas MTU.

## Desafío
Documentar el problema, implementar el pipeline y analizar los resultados para
proponer una solución medible y presentable al jurado.

## Cómo ejecutar el pipeline

### Requisitos

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/)
- Coloque los cuatro archivos fuente, no versionados, en `data/raw/`:
  `transactions.parquet`, `customer_mtu.parquet`,
  `policy_events.parquet` y `scam_reports.parquet`

Instale las dependencias:

```bash
uv sync --default-index https://pypi.org/simple
```

### Ejecución completa

Desde la raíz del repositorio:

```bash
uv run --frozen python -m pipeline run-all
```

Este comando limpia y valida los datos, reconstruye las features, crea el split
temporal, entrena el modelo, selecciona umbrales con validación y ejecuta la
comparación final sobre test.

### Ejecución por etapas

```bash
# 1. Validar y limpiar los cuatro Parquet
uv run --frozen python -m pipeline clean

# 2. Reconstruir MTD, enriquecer transacciones y crear model_data
uv run --frozen python -m pipeline prepare

# 3. Crear splits, entrenar el modelo y seleccionar umbrales en validación
uv run --frozen python -m pipeline train

# 4. Evaluar test contra P-01–P-05 y el baseline solo-MTU
uv run --frozen python -m pipeline evaluate
```

Cada etapa reutiliza la salida de la anterior. Para empezar desde cero, use
`run-all`.

### Salidas

El flujo conserva los Parquet originales y escribe:

- `data/processed/cleaned/`: fuentes validadas y reporte de calidad.
- `data/processed/prepared/`: `master.parquet`, `model_data.parquet` y validación MTU.
- `artifacts/splits/`: train (semanas 9–21), validación (22–23), test (24–26), IDs y checksums.
- `artifacts/fraud_model.joblib`: preprocesamiento y modelo entrenados.
- `artifacts/model_metadata.json`: features, medianas, versiones, métricas y umbrales.
- `artifacts/evaluation.json`, `policy_comparison.csv` y predicciones de test.

La pertenencia a cada split es determinista por tiempo; no se asignan filas al
azar. `random_state=42` controla únicamente las operaciones estocásticas del
modelo.

## Inferencia batch

La entrada debe contener las columnas de transacción del contrato, incluido el
acumulado causal `mtd_volume_before_mxn`. El comando rechaza lotes sin ese
historial en lugar de reconstruirlo a partir de una ventana incompleta.

```bash
uv run --frozen python -m pipeline predict \
  --transactions data/processed/cleaned/transactions.parquet \
  --customers data/processed/cleaned/customer_mtu.parquet \
  --output artifacts/predictions.parquet
```

La salida contiene `fraud_score`, riesgo estimado en MXN y decisión
`allow`/`warn`/`delay`.

## Verificación

```bash
uv run --frozen pytest -q
```

## Instrucciones adicionales
1. Revise la documentación en [`docs/`](docs/).
2. Consulte el contrato y los análisis en [`analytics/`](analytics/).
3. Abra el material visual en [`dashboard/`](dashboard/) y la presentación en
   [`pitch/`](pitch/).

## Índice
- [`docs/`](docs/): producto, backlog, arquitectura, métricas y decisiones.
- [`pipeline/`](pipeline/): ingesta, persistencia y evidencias de ejecución.
- [`analytics/`](analytics/): EDA, modelo, métricas y calidad de datos.
- [`dashboard/`](dashboard/): enlace o capturas de Amazon QuickSight.
- [`pitch/`](pitch/): material para la presentación final.
