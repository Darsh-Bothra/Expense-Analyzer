# AWS EC2 layout

```
Browser
  https://expenseanalyze.work.gd
       |
  Nginx on the EC2 host (80 → 443, Let’s Encrypt)
       |
  Next.js :5173  -->  FastAPI :8000   (Docker network, API_ORIGIN=http://backend:8000)
       |
  SQLite at /app/data/app.db  (volume backend-data)
```

The browser never talks to FastAPI directly. Next.js rewrites `/api/backend/*` at build time to `http://backend:8000` ([frontend/Dockerfile](../../frontend/Dockerfile) `ARG API_ORIGIN`).

## Instance

| Item | Value |
| --- | --- |
| Region | ap-south-1 (Mumbai) |
| OS | Ubuntu Server 24.04 |
| Size | t3.small (2 GB). t3.micro is tight for Next.js + pandas + an LLM call |
| SSH user | `ubuntu` |
| App directory on the VM | `~/Expense-Analyzer` |
| Domain | `expenseanalyze.work.gd` (A) and `www.expenseanalyze.work.gd` (CNAME) |
| DNS host | DNSExit (not Route 53) |

SSH from a laptop (key must not be world-readable):

```bash
chmod 400 ~/Downloads/expense-analyzer.pem
ssh -i ~/Downloads/expense-analyzer.pem ubuntu@<PUBLIC_OR_ELASTIC_IP>
```

Prefer an **Elastic IP** so Stop/Start does not change the address. If the public IP changes, update the DNS A record.

## Security group

| Type | Port | Source |
| --- | --- | --- |
| SSH | 22 | Your IP only |
| HTTP | 80 | `0.0.0.0/0` (Certbot + redirect) |
| HTTPS | 443 | `0.0.0.0/0` |

Do **not** expose **8000**. **5173** can stay closed to the world once Nginx is proxying; the UI is served on 443.

## Compose services

[docker-compose.yml](../../docker-compose.yml) on the VM:

- `backend` — FastAPI, health `GET /health`, volume `backend-data` → `/app/data`
- `frontend` — production `next start` on 5173

LLM settings come from the project-root `.env` on the VM (`chmod 600`). Do not commit that file. Repo defaults (if `.env` is missing) are `LLM_PROVIDER=openai` and `LLM_MODEL=gpt-4o-mini`. The **running** model is whatever is in the VM `.env`; changing it does not require a code change. See [operations.md](operations.md#changing-the-llm).

## Nginx

Host file `/etc/nginx/sites-available/expense-analyzer`, enabled, default site removed. Certbot adds the `listen 443 ssl` block.

```nginx
server {
    listen 80;
    server_name expenseanalyze.work.gd www.expenseanalyze.work.gd;
    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Certificate files: `/etc/letsencrypt/live/expenseanalyze.work.gd/`. Renewal is `certbot.timer`. HTTP-01 needs port **80** open.

If Certbot says it cannot find a matching server block, `server_name` is missing or the default site is still the only enabled site. Fix Nginx, then:

```bash
sudo certbot install --cert-name expenseanalyze.work.gd
```

Do not request a new certificate unless this one is gone.

## Frontend image

The production image uses `npm ci` then `next build` / `next start`. `package.json` and `package-lock.json` must stay in sync or the image build fails with `EUSAGE`. After adding npm packages locally:

```bash
cd frontend && npm install
```

Commit the updated lockfile before building on the VM.
