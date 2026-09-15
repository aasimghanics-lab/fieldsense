# Verification

The current source was exercised locally on 2026-09-15 using Docker Desktop/WSL2. The previous [Linux CI run](https://github.com/aasimghanics-lab/fieldsense/actions/runs/34879690802) tested an earlier source commit; its results are historical evidence, not pass counts for this revision.

## Reproduce

From an empty Compose project, run:

```sh
docker compose up --build -d --wait --wait-timeout 600
docker compose ps
curl --fail http://localhost:8080/api/health
docker compose exec -T backend sh -c 'ruff check . && ruff format --check . && pytest -q'
cd frontend && npm ci && npm run lint && npm test && npm run build && npx playwright install chromium && npx playwright test
```

From the repository root, export stored data and run R:

```sh
mkdir -p artifacts
curl --fail 'http://localhost:8080/api/exports/csv?measurement=soil_moisture' -o artifacts/readings.csv
docker compose --profile analysis run --rm analysis
test -s artifacts/r/plot-summary.csv
test -s artifacts/r/soil_moisture-treatments.png
docker compose exec -T backend python benchmarks.py
docker compose logs --tail 100
```

The initial local isolated run seeded 264,638 MongoDB readings across 192 PostgreSQL sensors, 24 plots, and 6 fields. Its pre-repair backend suite passed 25 tests, frontend unit suite 3 tests, and live Chromium suite 2 tests after the browser wait/selector repair. R generated 24 plot summaries and a treatment PNG from a 5.87 MB API export. The local benchmark measurements are in [BENCHMARKS.md](BENCHMARKS.md).

The initial fresh startup exposed a PostgreSQL health-check race: the PostGIS image briefly accepts Unix-socket connections during initialization, then restarts on TCP. The Compose health check now probes TCP and the application database.

## Final clean-room verification

`docker compose -p fieldsense_final up --build -d --wait --wait-timeout 600` rebuilt images and launched empty PostgreSQL and MongoDB volumes. Backend migration and seed completed without a connection failure. `docker compose -p fieldsense_final ps` showed PostgreSQL/PostGIS, MongoDB, FastAPI, and nginx all healthy. `/api/health` returned `ok` for PostgreSQL, PostGIS, and MongoDB. The dashboard reported 6 fields, 24 plots, 264,638 readings, 791 anomaly flags, and 6 offline sensors. The seeded unit API returned `°C` correctly.

- `docker compose -p fieldsense_final exec -T backend sh -c 'ruff check . && ruff format --check . && pytest -q'`: Ruff passed; **26 Python tests passed** against real databases. One Starlette/AnyIO test-client deprecation warning remains.
- `cd frontend && npm ci && npm run lint && npm test && npm run build`: lockfile install, TypeScript check, **3 Vitest tests**, and production build passed. npm reported zero vulnerabilities and the build emitted no large-chunk warning.
- `cd frontend && npx playwright test`: **3 Chromium tests passed** against the running app: exploration/map/chart/pagination/export, mobile navigation, and UI experiment creation plus note attachment.
- `docker compose -p fieldsense_final --profile analysis run --rm analysis`: a 5,744,860-byte CSV exported from the live API produced **24 plot summaries** and a treatment PNG.
- `docker compose -p fieldsense_final exec -T backend python benchmarks.py`: completed; exact results and methodology are in [BENCHMARKS.md](BENCHMARKS.md).
- `docker run --rm -v "${PWD}:/workspace" -w /workspace/infra hashicorp/terraform:1.10.5 init -backend=false` followed by `validate`: Terraform installed locked AWS provider 5.100.0 and reported a valid configuration, without AWS credentials.

Container logs showed successful migrations, seeding, health checks, HTTP requests, and benchmark ingestion. No backend traceback or container health failure occurred in the final project. PostgreSQL and MongoDB initialization emitted routine informational messages. The browser suite created a demo experiment and note in the final project's database. Benchmark documents were removed afterward.

No live AWS deployment, institutional login, scientific anomaly validation, high availability, or concurrent-user capacity is claimed.
