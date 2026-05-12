# Supabase Self-Host Setup Guide (Portainer)

## Prerequisites
- Docker + Portainer installed
- Stack directory created (e.g. `/home/<user>/documind/`)
Note: Change user with your path.
---

## Step 1 — Download Required Files

```bash
cd /home/<user>/documind

# Kong config
mkdir -p volumes/api volumes/db volumes/storage volumes/snippets volumes/functions volumes/logs volumes/pooler

# Download official volume files
curl -o volumes/api/kong.yml https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/api/kong.yml
curl -o volumes/api/kong-entrypoint.sh https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/api/kong-entrypoint.sh
curl -o volumes/db/realtime.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/realtime.sql
curl -o volumes/db/webhooks.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/webhooks.sql
curl -o volumes/db/roles.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/roles.sql
curl -o volumes/db/jwt.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/_supabase.sql
curl -o volumes/db/_supabase.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/_supabase.sql
curl -o volumes/db/logs.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/logs.sql
curl -o volumes/db/pooler.sql https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/db/pooler.sql
curl -o volumes/logs/vector.yml https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/logs/vector.yml
curl -o volumes/pooler/pooler.exs https://raw.githubusercontent.com/supabase/supabase/master/docker/volumes/pooler/pooler.exs

chmod +x volumes/api/kong-entrypoint.sh
sudo chown -R 999:999 /home/<user>/documind/volumes/db/data
```
Delete previous docker volumes for clean setup:
```bash
docker volume rm $(docker volume ls -q | grep supabase) 
```

---

## Step 2 — Fix DB Data Directory Ownership

**Do this every time before a fresh deploy.**

```bash
# Remove stale data (critical — old schema causes all auth issues)
sudo rm -rf /home/<user>/documind/volumes/db/data
sudo mkdir -p /home/<user>/documind/volumes/db/data
sudo chown -R 999:999 /home/<user>/documind/volumes/db/data

# Remove named Docker volume from previous deployments
docker volume rm supabase-local_db-config
# (ignore error if it doesn't exist)
```

---

## Step 3 — Environment Variables
Paste the docker-compose to portainer's web editor.
```yaml
name: supabase

services:

  studio:
    container_name: supabase-studio
    image: supabase/studio:2026.04.27-sha-5f60601
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "node -e \"fetch('http://localhost:3000/api/platform/profile').then((r) => {if (r.status !== 200) throw new Error(r.status)})\""
        ]
      timeout: 10s
      interval: 5s
      retries: 3
    depends_on:
      analytics:
        condition: service_healthy
    environment:
      HOSTNAME: "0.0.0.0"
      STUDIO_PG_META_URL: http://meta:8080
      POSTGRES_PORT: ${POSTGRES_PORT}
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PG_META_CRYPTO_KEY: ${PG_META_CRYPTO_KEY}
      PGRST_DB_SCHEMAS: ${PGRST_DB_SCHEMAS}
      PGRST_DB_MAX_ROWS: ${PGRST_DB_MAX_ROWS:-1000}
      PGRST_DB_EXTRA_SEARCH_PATH: ${PGRST_DB_EXTRA_SEARCH_PATH:-public}
      DEFAULT_ORGANIZATION_NAME: ${STUDIO_DEFAULT_ORGANIZATION}
      DEFAULT_PROJECT_NAME: ${STUDIO_DEFAULT_PROJECT}
      SUPABASE_URL: http://kong:8000
      SUPABASE_PUBLIC_URL: ${SUPABASE_PUBLIC_URL}
      SUPABASE_ANON_KEY: ${ANON_KEY}
      SUPABASE_SERVICE_KEY: ${SERVICE_ROLE_KEY}
      AUTH_JWT_SECRET: ${JWT_SECRET}
      LOGFLARE_API_KEY: ${LOGFLARE_PUBLIC_ACCESS_TOKEN}
      LOGFLARE_PUBLIC_ACCESS_TOKEN: ${LOGFLARE_PUBLIC_ACCESS_TOKEN}
      LOGFLARE_PRIVATE_ACCESS_TOKEN: ${LOGFLARE_PRIVATE_ACCESS_TOKEN}
      LOGFLARE_URL: http://analytics:4000
      NEXT_PUBLIC_ENABLE_LOGS: "true"
      NEXT_ANALYTICS_BACKEND_PROVIDER: postgres
      SNIPPETS_MANAGEMENT_FOLDER: /app/snippets
      EDGE_FUNCTIONS_MANAGEMENT_FOLDER: /app/edge-functions
    volumes:
      - /home/<user>/documind/volumes/snippets:/app/snippets:Z
      - /home/<user>/documind/volumes/functions:/app/edge-functions:Z

  kong:
    container_name: supabase-kong
    image: kong/kong:3.9.1
    restart: unless-stopped
    networks:
      default:
        aliases:
          - api-gw
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 5s
      timeout: 5s
      retries: 5
    depends_on:
      studio:
        condition: service_healthy
    ports:
      - ${KONG_HTTP_PORT}:8000/tcp
      - ${KONG_HTTPS_PORT}:8443/tcp
    volumes:
      - /home/<user>/documind/volumes/api/kong.yml:/home/kong/temp.yml:ro
      - /home/<user>/documind/volumes/api/kong-entrypoint.sh:/home/kong/kong-entrypoint.sh:ro
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /usr/local/kong/kong.yml
      KONG_DNS_ORDER: LAST,A,CNAME
      KONG_DNS_NOT_FOUND_TTL: 1
      KONG_PLUGINS: request-transformer,cors,key-auth,acl,basic-auth,request-termination,ip-restriction,post-function
      KONG_NGINX_PROXY_PROXY_BUFFER_SIZE: 160k
      KONG_NGINX_PROXY_PROXY_BUFFERS: 64 160k
      KONG_PROXY_ACCESS_LOG: /dev/stdout combined
      SUPABASE_ANON_KEY: ${ANON_KEY}
      SUPABASE_SERVICE_KEY: ${SERVICE_ROLE_KEY}
      SUPABASE_PUBLISHABLE_KEY: ${SUPABASE_PUBLISHABLE_KEY:-}
      SUPABASE_SECRET_KEY: ${SUPABASE_SECRET_KEY:-}
      ANON_KEY_ASYMMETRIC: ${ANON_KEY_ASYMMETRIC:-}
      SERVICE_ROLE_KEY_ASYMMETRIC: ${SERVICE_ROLE_KEY_ASYMMETRIC:-}
      DASHBOARD_USERNAME: ${DASHBOARD_USERNAME}
      DASHBOARD_PASSWORD: ${DASHBOARD_PASSWORD}
    entrypoint: /home/kong/kong-entrypoint.sh

  auth:
    container_name: supabase-auth
    image: supabase/gotrue:v2.186.0
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD",
          "wget",
          "--no-verbose",
          "--tries=1",
          "--spider",
          "http://localhost:9999/health"
        ]
      timeout: 5s
      interval: 5s
      retries: 3
    depends_on:
      db:
        condition: service_healthy
    environment:
      GOTRUE_API_HOST: 0.0.0.0
      GOTRUE_API_PORT: 9999
      API_EXTERNAL_URL: ${API_EXTERNAL_URL}
      GOTRUE_DB_DRIVER: postgres
      GOTRUE_DB_DATABASE_URL: postgres://supabase_auth_admin:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
      GOTRUE_SITE_URL: ${SITE_URL}
      GOTRUE_URI_ALLOW_LIST: ${ADDITIONAL_REDIRECT_URLS}
      GOTRUE_DISABLE_SIGNUP: ${DISABLE_SIGNUP}
      GOTRUE_JWT_ADMIN_ROLES: service_role
      GOTRUE_JWT_AUD: authenticated
      GOTRUE_JWT_DEFAULT_GROUP_NAME: authenticated
      GOTRUE_JWT_EXP: ${JWT_EXPIRY}
      GOTRUE_JWT_SECRET: ${JWT_SECRET}
      GOTRUE_EXTERNAL_EMAIL_ENABLED: ${ENABLE_EMAIL_SIGNUP}
      GOTRUE_EXTERNAL_ANONYMOUS_USERS_ENABLED: ${ENABLE_ANONYMOUS_USERS}
      GOTRUE_MAILER_AUTOCONFIRM: ${ENABLE_EMAIL_AUTOCONFIRM}
      GOTRUE_SMTP_ADMIN_EMAIL: ${SMTP_ADMIN_EMAIL}
      GOTRUE_SMTP_HOST: ${SMTP_HOST}
      GOTRUE_SMTP_PORT: ${SMTP_PORT}
      GOTRUE_SMTP_USER: ${SMTP_USER}
      GOTRUE_SMTP_PASS: ${SMTP_PASS}
      GOTRUE_SMTP_SENDER_NAME: ${SMTP_SENDER_NAME}
      GOTRUE_MAILER_URLPATHS_INVITE: ${MAILER_URLPATHS_INVITE}
      GOTRUE_MAILER_URLPATHS_CONFIRMATION: ${MAILER_URLPATHS_CONFIRMATION}
      GOTRUE_MAILER_URLPATHS_RECOVERY: ${MAILER_URLPATHS_RECOVERY}
      GOTRUE_MAILER_URLPATHS_EMAIL_CHANGE: ${MAILER_URLPATHS_EMAIL_CHANGE}
      GOTRUE_EXTERNAL_PHONE_ENABLED: ${ENABLE_PHONE_SIGNUP}
      GOTRUE_SMS_AUTOCONFIRM: ${ENABLE_PHONE_AUTOCONFIRM}

  rest:
    container_name: supabase-rest
    image: postgrest/postgrest:v14.8
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      PGRST_DB_URI: postgres://authenticator:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
      PGRST_DB_SCHEMAS: ${PGRST_DB_SCHEMAS}
      PGRST_DB_MAX_ROWS: ${PGRST_DB_MAX_ROWS:-1000}
      PGRST_DB_EXTRA_SEARCH_PATH: ${PGRST_DB_EXTRA_SEARCH_PATH:-public}
      PGRST_DB_ANON_ROLE: anon
      PGRST_JWT_SECRET: ${JWT_JWKS:-${JWT_SECRET}}
      PGRST_DB_USE_LEGACY_GUCS: "false"
      PGRST_APP_SETTINGS_JWT_SECRET: ${JWT_SECRET}
      PGRST_APP_SETTINGS_JWT_EXP: ${JWT_EXPIRY}
    command: ["postgrest"]

  realtime:
    container_name: realtime-dev.supabase-realtime
    image: supabase/realtime:v2.76.5
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "curl -sSfL --head -o /dev/null -H \"Authorization: Bearer ${ANON_KEY}\" http://localhost:4000/api/tenants/realtime-dev/health"
        ]
      timeout: 5s
      interval: 30s
      retries: 3
      start_period: 10s
    environment:
      PORT: 4000
      DB_HOST: ${POSTGRES_HOST}
      DB_PORT: ${POSTGRES_PORT}
      DB_USER: supabase_admin
      DB_PASSWORD: ${POSTGRES_PASSWORD}
      DB_NAME: ${POSTGRES_DB}
      DB_AFTER_CONNECT_QUERY: 'SET search_path TO _realtime'
      DB_ENC_KEY: supabaserealtime
      API_JWT_SECRET: ${JWT_SECRET}
      SECRET_KEY_BASE: ${SECRET_KEY_BASE}
      METRICS_JWT_SECRET: ${JWT_SECRET}
      ERL_AFLAGS: -proto_dist inet_tcp
      DNS_NODES: "''"
      RLIMIT_NOFILE: "10000"
      APP_NAME: realtime
      SEED_SELF_HOST: "true"
      RUN_JANITOR: "true"
      DISABLE_HEALTHCHECK_LOGGING: "true"

  storage:
    container_name: supabase-storage
    image: supabase/storage-api:v1.48.26
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      rest:
        condition: service_started
      imgproxy:
        condition: service_started
    healthcheck:
      test:
        [
          "CMD",
          "wget",
          "--no-verbose",
          "--tries=1",
          "--spider",
          "http://storage:5000/status"
        ]
      timeout: 5s
      interval: 5s
      retries: 3
      start_period: 10s
    environment:
      ANON_KEY: ${ANON_KEY}
      SERVICE_KEY: ${SERVICE_ROLE_KEY}
      POSTGREST_URL: http://rest:3000
      AUTH_JWT_SECRET: ${JWT_SECRET}
      DATABASE_URL: postgres://supabase_storage_admin:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
      STORAGE_PUBLIC_URL: ${SUPABASE_PUBLIC_URL}
      REQUEST_ALLOW_X_FORWARDED_PATH: "true"
      FILE_SIZE_LIMIT: 52428800
      STORAGE_BACKEND: file
      GLOBAL_S3_BUCKET: ${GLOBAL_S3_BUCKET}
      FILE_STORAGE_BACKEND_PATH: /var/lib/storage
      TENANT_ID: ${STORAGE_TENANT_ID}
      REGION: ${REGION}
      ENABLE_IMAGE_TRANSFORMATION: "true"
      IMGPROXY_URL: http://imgproxy:5001
      S3_PROTOCOL_ACCESS_KEY_ID: ${S3_PROTOCOL_ACCESS_KEY_ID}
      S3_PROTOCOL_ACCESS_KEY_SECRET: ${S3_PROTOCOL_ACCESS_KEY_SECRET}
    volumes:
      - /home/<user>/documind/volumes/storage:/var/lib/storage:z

  imgproxy:
    container_name: supabase-imgproxy
    image: darthsim/imgproxy:v3.30.1
    restart: unless-stopped
    volumes:
      - /home/<user>/documind/volumes/storage:/var/lib/storage:z
    healthcheck:
      test: ["CMD", "imgproxy", "health"]
      timeout: 5s
      interval: 5s
      retries: 3
    environment:
      IMGPROXY_BIND: ":5001"
      IMGPROXY_LOCAL_FILESYSTEM_ROOT: /
      IMGPROXY_USE_ETAG: "true"
      IMGPROXY_AUTO_WEBP: ${IMGPROXY_AUTO_WEBP}
      IMGPROXY_MAX_SRC_RESOLUTION: 16.8

  meta:
    container_name: supabase-meta
    image: supabase/postgres-meta:v0.96.3
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      PG_META_PORT: 8080
      PG_META_DB_HOST: ${POSTGRES_HOST}
      PG_META_DB_PORT: ${POSTGRES_PORT}
      PG_META_DB_NAME: ${POSTGRES_DB}
      PG_META_DB_USER: supabase_admin
      PG_META_DB_PASSWORD: ${POSTGRES_PASSWORD}
      CRYPTO_KEY: ${PG_META_CRYPTO_KEY}

  functions:
    container_name: supabase-edge-functions
    image: supabase/edge-runtime:v1.71.2
    restart: unless-stopped
    volumes:
      - /home/<user>/documind/volumes/functions:/home/deno/functions:Z
      - deno-cache:/root/.cache/deno
    depends_on:
      kong:
        condition: service_healthy
    environment:
      JWT_SECRET: ${JWT_SECRET}
      SUPABASE_URL: http://kong:8000
      SUPABASE_PUBLIC_URL: ${SUPABASE_PUBLIC_URL}
      SUPABASE_ANON_KEY: ${ANON_KEY}
      SUPABASE_SERVICE_ROLE_KEY: ${SERVICE_ROLE_KEY}
      SUPABASE_PUBLISHABLE_KEYS: "{\"default\":\"${SUPABASE_PUBLISHABLE_KEY:-}\"}"
      SUPABASE_SECRET_KEYS: "{\"default\":\"${SUPABASE_SECRET_KEY:-}\"}"
      SUPABASE_DB_URL: postgresql://postgres:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
      VERIFY_JWT: "${FUNCTIONS_VERIFY_JWT}"
    command: ["start", "--main-service", "/home/deno/functions/main"]

  analytics:
    container_name: supabase-analytics
    image: supabase/logflare:1.36.1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "http://localhost:4000/health"]
      timeout: 5s
      interval: 5s
      retries: 10
    depends_on:
      db:
        condition: service_healthy
    environment:
      LOGFLARE_NODE_HOST: 127.0.0.1
      DB_USERNAME: supabase_admin
      DB_DATABASE: _supabase
      DB_HOSTNAME: ${POSTGRES_HOST}
      DB_PORT: ${POSTGRES_PORT}
      DB_PASSWORD: ${POSTGRES_PASSWORD}
      DB_SCHEMA: _analytics
      LOGFLARE_PUBLIC_ACCESS_TOKEN: ${LOGFLARE_PUBLIC_ACCESS_TOKEN}
      LOGFLARE_PRIVATE_ACCESS_TOKEN: ${LOGFLARE_PRIVATE_ACCESS_TOKEN}
      LOGFLARE_SINGLE_TENANT: "true"
      LOGFLARE_SUPABASE_MODE: "true"
      POSTGRES_BACKEND_URL: postgresql://supabase_admin:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/_supabase
      POSTGRES_BACKEND_SCHEMA: _analytics
      LOGFLARE_FEATURE_FLAG_OVERRIDE: multibackend=true

  db:
    container_name: supabase-db
    image: supabase/postgres:15.8.1.121
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - /home/<user>/documind/volumes/db/realtime.sql:/docker-entrypoint-initdb.d/migrations/99-realtime.sql:Z
      - /home/<user>/documind/volumes/db/webhooks.sql:/docker-entrypoint-initdb.d/init-scripts/98-webhooks.sql:Z
      - /home/<user>/documind/volumes/db/roles.sql:/docker-entrypoint-initdb.d/init-scripts/99-roles.sql:Z
      - /home/<user>/documind/volumes/db/jwt.sql:/docker-entrypoint-initdb.d/init-scripts/99-jwt.sql:Z
      - /home/<user>/documind/volumes/db/data:/var/lib/postgresql/data:Z
      - /home/<user>/documind/volumes/db/_supabase.sql:/docker-entrypoint-initdb.d/migrations/97-_supabase.sql:Z
      - /home/<user>/documind/volumes/db/logs.sql:/docker-entrypoint-initdb.d/migrations/99-logs.sql:Z
      - /home/<user>/documind/volumes/db/pooler.sql:/docker-entrypoint-initdb.d/migrations/99-pooler.sql:Z
      - db-config:/etc/postgresql-custom
    environment:
      POSTGRES_HOST: /var/run/postgresql
      PGPORT: ${POSTGRES_PORT}
      POSTGRES_PORT: ${POSTGRES_PORT}
      PGPASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATABASE: ${POSTGRES_DB}
      POSTGRES_DB: ${POSTGRES_DB}
      JWT_SECRET: ${JWT_SECRET}
      JWT_EXP: ${JWT_EXPIRY}
    command:
      [
        "postgres",
        "-c",
        "config_file=/etc/postgresql/postgresql.conf",
        "-c",
        "log_min_messages=fatal"
      ]

  vector:
    container_name: supabase-vector
    image: timberio/vector:0.53.0-alpine
    restart: unless-stopped
    volumes:
      - /home/<user>/documind/volumes/logs/vector.yml:/etc/vector/vector.yml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    healthcheck:
      test:
        [
          "CMD",
          "wget",
          "--no-verbose",
          "--tries=1",
          "--spider",
          "http://vector:9001/health"
        ]
      timeout: 5s
      interval: 5s
      retries: 3
    environment:
      LOGFLARE_PUBLIC_ACCESS_TOKEN: ${LOGFLARE_PUBLIC_ACCESS_TOKEN}
    command: ["--config", "/etc/vector/vector.yml"]
    security_opt:
      - "label=disable"

  supavisor:
    container_name: supabase-pooler
    image: supabase/supavisor:2.7.4
    restart: unless-stopped
    ports:
      - ${POSTGRES_PORT}:5432
      - ${POOLER_PROXY_PORT_TRANSACTION}:6543
    volumes:
      - /home/<user>/documind/volumes/pooler/pooler.exs:/etc/pooler/pooler.exs:ro
    healthcheck:
      test:
        [
          "CMD",
          "curl",
          "-sSfL",
          "--head",
          "-o",
          "/dev/null",
          "http://127.0.0.1:4000/api/health"
        ]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    depends_on:
      db:
        condition: service_healthy
    environment:
      PORT: 4000
      POSTGRES_PORT: ${POSTGRES_PORT}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      DATABASE_URL: ecto://supabase_admin:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/_supabase
      CLUSTER_POSTGRES: "true"
      SECRET_KEY_BASE: ${SECRET_KEY_BASE}
      VAULT_ENC_KEY: ${VAULT_ENC_KEY}
      API_JWT_SECRET: ${JWT_SECRET}
      METRICS_JWT_SECRET: ${JWT_SECRET}
      REGION: local
      ERL_AFLAGS: -proto_dist inet_tcp
      POOLER_TENANT_ID: ${POOLER_TENANT_ID}
      POOLER_DEFAULT_POOL_SIZE: ${POOLER_DEFAULT_POOL_SIZE}
      POOLER_MAX_CLIENT_CONN: ${POOLER_MAX_CLIENT_CONN}
      POOLER_POOL_MODE: transaction
      DB_POOL_SIZE: ${POOLER_DB_POOL_SIZE}
    command:
      [
        "/bin/sh",
        "-c",
        "/app/bin/migrate && /app/bin/supavisor eval \"$$(cat /etc/pooler/pooler.exs)\" && /app/bin/server"
      ]

volumes:
  db-config:
  deno-cache:
```


Paste these into Portainer's **Advanced > Environment** section.  
Replace all `<placeholder>` values with your own.

```env
# Database
POSTGRES_PASSWORD=<your-password>
POSTGRES_PORT=5432
POSTGRES_HOST=db
POSTGRES_DB=postgres
PG_META_CRYPTO_KEY=<32-char-min-random-string>

# Auth & JWT
JWT_SECRET=<32-char-min-random-string>
JWT_EXPIRY=3600
ANON_KEY=<generated-anon-jwt>
SERVICE_ROLE_KEY=<generated-service-role-jwt>
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8001

# Kong Gateway
KONG_HTTP_PORT=8001
KONG_HTTPS_PORT=8443
DASHBOARD_USERNAME=supabase
DASHBOARD_PASSWORD=<your-password>

# Studio
SUPABASE_PUBLIC_URL=http://localhost:8001
STUDIO_DEFAULT_ORGANIZATION=<your-org>
STUDIO_DEFAULT_PROJECT=<your-project>
SNIPPETS_MANAGEMENT_FOLDER=/app/snippets
EDGE_FUNCTIONS_MANAGEMENT_FOLDER=/app/functions
OPENAI_API_KEY=

# PostgREST
PGRST_DB_SCHEMAS=public,storage,graphql_public
PGRST_DB_MAX_ROWS=1000
PGRST_DB_EXTRA_SEARCH_PATH=public

# Analytics (Logflare)
LOGFLARE_PUBLIC_ACCESS_TOKEN=<random-string>
LOGFLARE_PRIVATE_ACCESS_TOKEN=<random-string>

# Storage
S3_PROTOCOL_ACCESS_KEY_ID=<random-hex-32>
S3_PROTOCOL_ACCESS_KEY_SECRET=<random-hex-64>
REGION=us-east-1
GLOBAL_S3_BUCKET=<your-bucket-name>
STORAGE_TENANT_ID=stub

# Supavisor (Pooler)
SECRET_KEY_BASE=<64-char-random-string>
VAULT_ENC_KEY=<32-char-random-string>
POOLER_PROXY_PORT_TRANSACTION=6543
POOLER_DEFAULT_POOL_SIZE=20
POOLER_MAX_CLIENT_CONN=100
POOLER_TENANT_ID=default
POOLER_DB_POOL_SIZE=5

# Auth booleans — MUST all be explicitly set, never empty
ENABLE_ANONYMOUS_USERS=false
ENABLE_EMAIL_SIGNUP=true
ENABLE_EMAIL_AUTOCONFIRM=false
ENABLE_PHONE_SIGNUP=true
ENABLE_PHONE_AUTOCONFIRM=true
DISABLE_SIGNUP=false

# SMTP — use placeholders if not using real email
SMTP_HOST=supabase-mail
SMTP_PORT=2500
SMTP_USER=fake_mail_user
SMTP_PASS=fake_mail_password
SMTP_SENDER_NAME=fake_sender
SMTP_ADMIN_EMAIL=admin@example.com
MAILER_URLPATHS_CONFIRMATION=/auth/v1/verify
MAILER_URLPATHS_INVITE=/auth/v1/verify
MAILER_URLPATHS_RECOVERY=/auth/v1/verify
MAILER_URLPATHS_EMAIL_CHANGE=/auth/v1/verify

# Edge Functions
FUNCTIONS_VERIFY_JWT=false

# Misc
IMGPROXY_AUTO_WEBP=true
DOCKER_SOCKET_LOCATION=/var/run/docker.sock
ADDITIONAL_REDIRECT_URLS=
```

> ⚠️ **All boolean env vars must have explicit `true`/`false` values. Empty string will crash GoTrue.**  
> ⚠️ **All integer env vars (e.g. `SMTP_PORT`) must have a value. Empty string will crash GoTrue.**

---

## Step 4 — Deploy the Stack in Portainer

1. Go to Portainer → Stacks → Add Stack
2. Paste the `docker-compose.yml` (use absolute paths — `./` does not work in Portainer)
3. Paste env vars in Advanced mode
4. Click Deploy

---

## Step 5 — Fix Authentication Schema (CRITICAL)

The `supabase/postgres:15.8.1.085` image ships with a 2018-era auth schema. GoTrue v2.x expects a modern schema. After first deploy, the auth container will crash. Fix it as follows.

### 5a — Clear migration history so GoTrue reruns everything

```bash
docker exec -it supabase-db psql -U supabase_admin -d postgres
```

```sql
DELETE FROM auth.schema_migrations;
\q
```

```bash
docker restart supabase-auth
```

### 5b — Watch logs for failing migrations

```bash
docker logs -f supabase-auth
```

GoTrue will now apply all 67+ migrations automatically. If it crashes on a specific migration, you'll see a line like:

```
error executing migrations/20250731150234_add_oauth_clients_table.up.sql ... ERROR: column "client_id" does not exist
```

### 5c — Skip broken migrations manually

For each failing migration, grab the version number from the filename (e.g. `20250731150234`) and run:

```bash
docker exec -it supabase-db psql -U supabase_admin -d postgres
```

```sql
INSERT INTO auth.schema_migrations (version) VALUES ('<version>') ON CONFLICT DO NOTHING;
\q
```

```bash
docker restart supabase-auth
```

Repeat until you see:

```
Migrations already up to date, nothing to apply
GoTrue API started on: 0.0.0.0:9999
```

### Known broken migrations (as of GoTrue v2.186.0 + postgres:15.8.1.085)

Skip all of these in one go if needed:

```sql
INSERT INTO auth.schema_migrations (version) VALUES 
('20250731150234'),
('20250904133000'),
('20251007112900'),
('20251104100000'),
('20251111201300')
ON CONFLICT DO NOTHING;
```

Then restart auth.

---

## Step 6 — Verify Everything is Working

```bash
# Check all containers are running
docker ps | grep supabase

# Check auth is healthy
docker logs supabase-auth --tail 5

# Check analytics is healthy
docker exec supabase-db curl -s http://analytics:4000/health
```

Open Studio at `http://localhost:8001` — Authentication → Users should load without errors.

---

## Known Non-Issues

| Error | Cause | Action |
|---|---|---|
| `Failed to load log drains` | Cloud-only feature, not available in self-hosted | Ignore |
| GoTrue deprecation warnings about `GOTRUE_JWT_ADMIN_GROUP_NAME` | Harmless | Ignore |
| analytics MIME library warning on startup | Harmless | Ignore |

---

## Key Lessons

- **Always** wipe `volumes/db/data` and fix ownership (`chown 999:999`) before a fresh deploy
- **Always** delete the `supabase-local_db-config` Docker named volume before redeploying
- **Never** use `docker volume prune` — it affects all containers system-wide; use `docker compose down -v` instead
- The `supabase/postgres` image ignores mounted SQL files on an existing data directory — schema is baked into the image
- All service image versions must be from the same official release to avoid schema mismatches
- In Portainer, `${PWD}` does not resolve — always use absolute paths in volumes
- Boolean and integer env vars passed as empty strings will crash GoTrue on startup
