# Measured benchmarks

Measured on 2026-09-14 in [GitHub Actions run 34879690802](https://github.com/aasimghanics-lab/fieldsense/actions/runs/34879690802), source commit `95485b5dbf90772c87f4d58c5887e5a2eb2155d1`. These are Docker Compose measurements on a hosted Linux runner, **not AWS production measurements or local Windows results**.

Environment: Linux 6.17.0-1022-azure, Python 3.12.14, 4 visible vCPUs on Intel Xeon 6973P-C hardware, 16,372,440 kB reported memory. PostgreSQL/PostGIS, MongoDB, FastAPI and nginx shared the runner. Dataset: **264,638 simulated readings, 192 sensors, 24 plots and 6 fields**.

| HTTP workload | Samples | Median (ms) | p95 (ms) |
|---|---:|---:|---:|
| Recent sensor readings | 20 | 5.92 | 6.39 |
| Time aggregation | 20 | 67.77 | 77.11 |
| Dashboard | 20 | 125.35 | 129.90 |
| Spatial bounding-box lookup | 20 | 12.03 | 12.89 |

One 1,000-row ingestion batch took **87.24 ms**, or **11,463.02 rows/second**. This single batch is not a throughput capacity estimate. Benchmark documents were removed afterward.

## Reproduce and inspect

Run `docker compose exec -T backend python benchmarks.py`. Read workloads perform one warmup and 20 sequential HTTP requests. Time includes nginx, serialization and database work; p95 is the nearest-rank 19th sample. Bulk ingestion is measured once. The runner had no concurrent load generator.

The [research-validation artifact](https://github.com/aasimghanics-lab/fieldsense/actions/runs/34879690802/artifacts/10362014292) contains the original JSON report, actual exported readings, R summary CSV and generated PNG. CI reruns this suite and retains fresh artifacts under each run. GitHub artifact retention applies.

Runner variability, warm caches, a single client, small sample counts and simulated data limit generalization. These establish reproducible functionality and a baseline, not scientific validation, an SLA or concurrent-user capacity.

The original Windows attempt had a full C: drive and WSL failed to start. That attempt produced no measurements; the local Docker Desktop reproduction below is a separate later run.

## Local Docker Desktop reproduction (2026-09-15)

The same command, `docker compose -p fieldsense_audit exec -T backend python benchmarks.py`, ran against a fresh isolated Compose stack seeded with 264,638 readings. Host: Windows/Docker Desktop with Linux 6.6.87.2 WSL2, 8 visible vCPUs on an Intel Core i5-1135G7, and 3,868,900 kB reported container memory. Python was 3.12.14. PostgreSQL, MongoDB, backend, and nginx shared this machine. One warmup preceded 20 sequential HTTP samples for each read route; nearest-rank p95 is the 19th ordered sample. The single 1,000-row batch was removed after measurement.

| HTTP workload | Samples | Median (ms) | p95 (ms) |
|---|---:|---:|---:|
| Recent sensor readings | 20 | 18.07 | 26.44 |
| Time aggregation | 20 | 165.80 | 203.54 |
| Dashboard | 20 | 304.03 | 384.74 |
| Spatial bounding-box lookup | 20 | 46.97 | 65.31 |

The ingestion batch took 285.61 ms, equivalent to 3,501.27 rows/second for this one batch. These local results do not reproduce the earlier CI latencies; runner hardware, memory, caches, and concurrent host activity differ. No SLA or sustained throughput is inferred.

## Final clean-room project (2026-09-15)

After stopping the audit project, `docker compose -p fieldsense_final up --build -d --wait --wait-timeout 600` created empty database volumes and seeded the same 264,638 readings. After the complete test and R workflows, `docker compose -p fieldsense_final exec -T backend python benchmarks.py` produced the following independent run on the same WSL2 host and 3,868,900 kB container memory. Methodology and route definitions are unchanged; each read workload has one warmup and 20 sequential HTTP samples.

| HTTP workload | Samples | Median (ms) | p95 (ms) |
|---|---:|---:|---:|
| Recent sensor readings | 20 | 16.01 | 17.87 |
| Time aggregation | 20 | 174.17 | 194.14 |
| Dashboard | 20 | 237.85 | 311.17 |
| Spatial bounding-box lookup | 20 | 33.24 | 39.46 |

The one 1,000-row ingestion batch took 140.35 ms (7,125.04 rows/second for that batch). Its benchmark documents were removed. Differences between the two local runs show why neither is a capacity or latency guarantee.
