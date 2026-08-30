# Operations

Commands below run **on the EC2 VM** unless marked as laptop. App dir: `~/Expense-Analyzer`.

## Day-to-day

**Cost.** You pay while the instance is **running**. EC2 console → **Stop** when idle. You still pay a little for the disk (and an Elastic IP if allocated). **Terminate** deletes the VM and SQLite unless you have a snapshot.

**Health.**

```bash
cd ~/Expense-Analyzer
docker compose ps
docker compose logs -f --tail=80
curl -I https://expenseanalyze.work.gd
```

Both containers should be `healthy`. `curl` should be `200` (or a short redirect).

**Secrets.** Edit `~/Expense-Analyzer/.env` only on the VM. After a change:

```bash
cd ~/Expense-Analyzer
docker compose up -d
```

That recreates containers with the new env. The SQLite volume is kept. No image rebuild.

**TLS.** Auto-renews if port 80 stays open. Check: `sudo certbot renew --dry-run`.

**No login.** Anyone with the URL can upload. Treat it as a demo.

## SQLite

Uploads, chat, and observability live in Compose volume `backend-data`.

| Action | Data |
| --- | --- |
| `docker compose up --build -d` | **Kept** |
| `docker compose down` (no `-v`) | **Kept** |
| `docker compose down -v` | **Deleted** |
| Stop instance | **Kept** (EBS) |
| Terminate instance | **Lost** unless snapshotted |

Backup:

```bash
cd ~/Expense-Analyzer
docker compose cp backend:/app/data/app.db ./app.db.backup
```

From the laptop:

```bash
scp -i ~/Downloads/expense-analyzer.pem \
  ubuntu@<IP>:~/Expense-Analyzer/app.db.backup .
```

## Changing the LLM

No code change. Provider, model, and key are env-only ([docs/architecture.md](../architecture.md#switch-llm-env-only)).

On the VM, edit `~/Expense-Analyzer/.env`. Examples:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=...
```

`langchain-openai` and `langchain-groq` are already in backend deps. For Google or Anthropic, install the matching `langchain-*` package in the backend image (that **does** need a rebuild).

Then:

```bash
cd ~/Expense-Analyzer
docker compose up -d
docker compose logs backend --tail=40
```

The live site uses this file, not the defaults in [docker-compose.yml](../../docker-compose.yml) or [backend/.env.example](../../backend/.env.example). Observability cost estimates use a small table in `backend/app/observability/tracker.py`; unknown model names report `0` cost.

## Shipping code

Laptop: commit and push (include `frontend/package-lock.json` if npm deps changed).

VM:

```bash
cd ~/Expense-Analyzer
git pull
docker compose up --build -d
docker compose ps
```

If the VM has no git remote, rsync from the laptop (do not overwrite the server `.env` unless you mean to):

```bash
rsync -avz \
  --exclude node_modules --exclude .git --exclude backend/.venv --exclude frontend/.next \
  -e "ssh -i ~/Downloads/expense-analyzer.pem" \
  /path/to/assignment-npci/ \
  ubuntu@<IP>:~/Expense-Analyzer/
```

Then `docker compose up --build -d` on the VM.

Nginx and Let’s Encrypt stay on the host. You do **not** rerun Certbot for a normal app update.

Smoke-test https://expenseanalyze.work.gd (upload or reopen a dataset).

| Change | Command |
| --- | --- |
| App code, Dockerfile, Python/npm deps | `git pull` then `docker compose up --build -d` |
| `.env` only (model, keys, analyze limits) | `docker compose up -d` |
| Nginx `server_name` | edit site file, `sudo nginx -t && sudo systemctl reload nginx` |
| Extra hostname on the cert | `sudo certbot --nginx -d expenseanalyze.work.gd -d www.expenseanalyze.work.gd` |

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Tab spins on `https://` | Security group missing **443**, or Nginx not listening on 443 |
| `http://` 301 then hang | 443 still closed; redirect is fine, TLS is not reachable |
| Nginx 404 on `/` | `server_name` missing; default site still enabled |
| Certbot: no matching server block | Fix `server_name`, then `sudo certbot install --cert-name expenseanalyze.work.gd` |
| Upload fails, UI loads | `docker compose logs backend --tail=80` |
| `npm ci` / `EUSAGE` | Lockfile stale — `cd frontend && npm install`, commit lockfile |
| Empty chat/datasets | `down -v` or instance terminated |
| SSH unprotected key | `chmod 400` on the `.pem` |
| Site dead after Stop/Start | Public IP changed; fix A record or use Elastic IP |

On the VM:

```bash
sudo ss -lntp | grep -E ':80|:443|:5173'
curl -sS -o /dev/null -w "local80=%{http_code}\n" -H "Host: expenseanalyze.work.gd" http://127.0.0.1/
curl -sS -o /dev/null -w "local5173=%{http_code}\n" http://127.0.0.1:5173/
```

Healthy: Nginx on 80 and 443, `local80=301` (HTTPS redirect), `local5173=200`.
