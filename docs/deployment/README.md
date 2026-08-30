# Deployment

Expense Analyzer on AWS: one Ubuntu EC2 instance, Docker Compose, Nginx, and Let’s Encrypt. SQLite stays on the instance disk (Compose volume `backend-data`), so app rebuilds do not wipe uploads or chat.

Live URL: [https://expenseanalyze.work.gd](https://expenseanalyze.work.gd)

| File | Contents |
| --- | --- |
| [aws-ec2.md](aws-ec2.md) | What is running, DNS, TLS, security group, first-time layout |
| [operations.md](operations.md) | Day-to-day ops, changing the LLM, shipping code, troubleshooting |

This is a single-VM demo. There is no auth. Anyone who can open the URL can upload files.

App Runner / Fargate are not used: those replace the container filesystem on deploy and would flush SQLite. See [operations.md](operations.md#sqlite).
