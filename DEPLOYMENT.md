# Deployment

## Local

Run `docker compose up --build`. Open http://localhost:8080. The first startup applies Alembic migrations, creates MongoDB indexes and loads simulated data; subsequent starts preserve volumes. Docker must have sufficient free storage and memory. The default write token is `local-write-token-change-before-hosting` and is for loopback development only.

Optional configuration: copy `.env.example` to `.env`. Keep database password and DATABASE_URL synchronized. Never commit `.env`. Stop with `docker compose down`; adding `-v` permanently deletes research volumes.

Run the continuous simulator in another terminal:

```sh
docker compose exec backend python -m app.simulator
```

## AWS single-host path

The Terraform configuration provisions an Amazon Linux EC2 host, encrypted EBS, a static public IP, an HTTP/HTTPS-only security group and an SSM instance role. It clones this repository, generates random credentials and starts the Compose stack behind Caddy. This is a low-complexity single-host architecture, not high availability. A default VPC with an internet-connected subnet is required. Cloud resources incur charges.

Install AWS CLI v2 and Terraform 1.6 or later. Authenticate and deploy:

```sh
aws configure sso
aws sso login --profile fieldsense
export AWS_PROFILE=fieldsense
terraform -chdir=infra init
terraform -chdir=infra plan -var='domain=fieldsense.your-domain.edu'
terraform -chdir=infra apply -var='domain=fieldsense.your-domain.edu'
```

PowerShell equivalent for the profile is `$env:AWS_PROFILE='fieldsense'`. Point the domain's DNS A record at `terraform -chdir=infra output -raw public_ip`. Caddy acquires a public TLS certificate after DNS resolves. Verify:

```sh
curl --fail https://fieldsense.your-domain.edu/api/health
curl --fail https://fieldsense.your-domain.edu/api/dashboard
```

Use SSM Session Manager to inspect `/var/log/cloud-init-output.log`, `/opt/fieldsense/.env`, and `docker compose logs`; do not print secrets into public logs. Keep Terraform state private. No inbound SSH or database ports are opened.

## Operations

Before storing real research data, configure institutional access control, backups, retention and recovery procedures. The portfolio deployment is publicly readable. Copy `pg_dump` and `mongodump` backups to encrypted off-host storage, test restores, and schedule them according to the lab's recovery requirements. EBS alone is not a backup. For updates, take backups, review the commit, pull it, then run `docker compose -f compose.yaml -f infra/compose.production.yaml up --build -d`. Review migrations before applying to non-demo data.

For a managed architecture, move PostgreSQL/PostGIS to RDS, documents to MongoDB Atlas, and application containers to ECS; supply DATABASE_URL and MONGO_URL through a secret manager. That architecture is a documented extension, not provisioned by this repository.

No AWS deployment is claimed without a verified public URL. Sites Worker hosting cannot host this Python/PostGIS/MongoDB application as provided.
