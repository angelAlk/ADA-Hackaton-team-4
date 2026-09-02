# Decision log

| Fecha | Decisión | Contexto | Impacto | Responsable |
| --- | --- | --- | --- | --- |
| 2026-09-01 | Estructurar entregables por área | Facilitar la evaluación del jurado | Navegación clara del repositorio | Equipo 4 |
| 2026-09-02 | Pipeline local en pandas y scikit-learn | El notebook depende de Databricks y rutas personales | Entrenamiento e inferencia ejecutables desde CLI | Ingeniería |
| 2026-09-02 | Split temporal train 9–21, validación 22–23, test 24–26 | Se necesita validación sin contaminar el cambio de régimen final | Hiperparámetros y umbrales no usan test | Ingeniería/BA |
| 2026-09-02 | Reproducibilidad por cortes e IDs, no por muestreo aleatorio | Un seed no define correctamente un split temporal | Manifiestos con IDs, conteos y SHA-256; semilla 42 solo para el modelo | Ingeniería |
| 2026-09-02 | Todas las transacciones suman al MTD | Esta variante reproduce el Parquet; excluir no completadas difiere hasta MXN 241,882.60 | La reconstrucción usa todos los montos y excluye solo la fila actual | Ingeniería |
| 2026-09-02 | Tolerancia MTU de MXN 0.10 | El acumulado fuente float32 difiere hasta MXN 0.0625 por representación | Se aceptan diferencias de almacenamiento, no cambios semánticos | Ingeniería |
| 2026-09-02 | Imputación ajustada exclusivamente en train | El notebook calculaba medianas antes del split | Evita fuga de validación/test y persiste medianas | Ingeniería |
| 2026-09-02 | Columnas post-acción fuera del modelo | Solo existen después de aplicar la política vigente | Se usan únicamente al derivar costos/efectividad | Ingeniería/BA |
| 2026-09-02 | Umbrales seleccionados en validación por valor neto | Optimizar en test produce una comparación optimista | Test queda reservado para la comparación final | BA |
| 2026-09-02 | Inferencia exige `mtd_volume_before_mxn` causal | Un lote parcial no permite reconstruir historia mensual correcta | Fallo explícito ante historial ausente | Ingeniería |
