# Contributing

Use short-lived branches and focused commits. Describe the research workflow affected, behavior before/after, and actual verification. Do not include real participant, farmer, location or device secrets in fixtures.

Start the stack with `docker compose up --build -d --wait`. Run:

```sh
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
cd frontend
npm install
npm run lint
npm test
npm run build
```

Integration tests require the seeded demo database and clean up their own inserted readings/experiments. Never point this suite at a real research database. Put schema changes in new Alembic revisions, preserve stable identifiers, validate timezone-aware timestamps and keep aggregation/export limits. Test changes against both databases; SQLite and document mocks cannot validate PostGIS or MongoDB aggregation semantics.

Use `ruff format` for Python. Do not check in `.env`, node_modules, database files, exported raw datasets or Terraform state. Update architecture and operational documentation when data ownership or access changes. Describe simulated data and benchmark environments explicitly.
