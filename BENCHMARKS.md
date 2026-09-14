# Benchmarks

No measured results have been recorded yet. The reproducible suite is `docker compose exec -T backend python benchmarks.py`. It performs 20 sequential requests after one warmup for recent readings, chart aggregation, dashboard and a geospatial bounding-box query, plus one 1,000-row ingestion batch that is removed afterward.

The report captures UTC time, container platform, Python version, CPU count and dataset size. It reports median and nearest-rank p95 wall time; ingestion reports elapsed time and rows/second. These are single-client HTTP measurements, not concurrent-user capacity or production SLA evidence. GitHub Actions saves actual JSON results and R outputs as the `research-validation` artifact.

Local verification on the initial Windows host was blocked by a full C: drive and a WSL startup error. No latency or throughput numbers are inferred from that attempt.
