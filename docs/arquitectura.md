# Arquitectura

```text
Parquet crudo
  → clean (esquema, PK/FK, timestamps)
  → prepare (MTD, joins, features)
  → split temporal (train/validación/test + manifiestos)
  → train (imputador + GBM + artefacto)
  → validación (umbrales y guardrails)
  → evaluación test (modelo vs P-01–P-05 vs MTU)
  → predict (score, riesgo MXN, decisión)
```

## Componentes
- **`pipeline/data.py`:** valida y limpia sin modificar fuentes.
- **`pipeline/features.py`:** reconstruye MTD, construye `master` y
  `model_data`, y aplica la allowlist.
- **`pipeline/split.py`:** corta por semana ISO y persiste IDs/checksums.
- **`pipeline/model.py`:** ajusta preprocesamiento y GBM; serializa con joblib.
- **`pipeline/evaluation.py`:** selecciona umbrales en validación y compara
  políticas en test.
- **`pipeline/inference.py`:** API batch validada.
- **`pipeline/cli.py`:** orquesta etapas locales mediante `python -m pipeline`.

Los datos preparados y artefactos ejecutados están ignorados por git; código,
lockfile, contrato, pruebas y decisiones sí se versionan.
