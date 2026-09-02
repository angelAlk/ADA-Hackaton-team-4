# Datos fuente

Coloque en este directorio los cuatro archivos Parquet antes de ejecutar el
pipeline:

- `transactions.parquet`
- `customer_mtu.parquet`
- `policy_events.parquet`
- `scam_reports.parquet`

Los Parquet están excluidos de Git. No coloque aquí datos procesados; el
pipeline los genera bajo `data/processed/`.
