# Controles de calidad

| Control | Regla | Resultado | Acción ante falla |
| --- | --- | --- | --- |
| Esquema | Columnas requeridas presentes | Cumple en 4 fuentes | Detener ejecución |
| Completitud | Campos requeridos sin nulos | 0 nulos | Detener ejecución y reportar por columna |
| Duplicados exactos | Filas idénticas | 0 removidas | Remover antes de validar claves |
| Claves primarias | `txn_id`, `customer_id`, `event_id`, `report_id` únicos | Cumple | Detener ejecución |
| Claves foráneas | Eventos/reportes existen en transacciones; clientes existen | 100% de cobertura | Detener ejecución |
| Grano de master | Un registro por `txn_id` | 901,286 filas y IDs únicos | Detener ejecución |
| Acumulado MTU | Reconstrucción excluye fila actual y reinicia por mes | Variante de todas las transacciones coincide; diferencia máxima float32 MXN 0.0625 | Detener si excede MXN 0.10 |
| Split temporal | Cada ID pertenece exactamente a un conjunto | 637,487 train; 104,959 validación; 158,840 test | Detener ejecución |
| Repetibilidad | SHA-256 de IDs por split estable | Registrado en `split_manifest.json` | Detener ante cambio inesperado |
| Fuga | Features contra allowlist | 18 fuentes permitidas; post-acción excluidas | Detener pruebas |

Los detalles legibles por máquina se escriben en
`data/processed/cleaned/quality_report.json`,
`data/processed/prepared/feature_report.json` y
`artifacts/splits/split_manifest.json`.
