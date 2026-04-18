# Competitor Intelligence Agent — Complete Guide
## From zero to deployed on AWS, step by step

---

## What this system does

Every 30 minutes, 4 AI agents run in parallel and monitor your competitors:

| Agent | Data Source | What it tracks |
|---|---|---|
| Blog Monitor | RSS feeds + Groq AI | New posts, sentiment, keywords |
| YouTube Monitor | YouTube Data API | New videos, views, likes, comments |
| Reddit Monitor | Reddit API + Groq AI | Brand mentions, public sentiment |
| Meta Ads Monitor | Meta Ad Library API | New ads, platforms, creative |

You get: instant email/Slack alerts + Grafana dashboard + MLflow experiment tracking + evaluation scores.

---

## PART 1 — Get your free API keys (30 minutes)

### 1.1 Groq API (free AI — replaces OpenAI)
1. Go to https://console.groq.com
2. Sign up → Dashboard → API Keys → Create API Key
3. Copy the key → goes into `.env` as `GROQ_API_KEY`

### 1.2 YouTube Data API (free — 10,000 requests/day)
1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "CompetitorIntel")
3. APIs & Services → Enable APIs → search "YouTube Data API v3" → Enable
4. APIs & Services → Credentials → Create Credentials → API Key
5. Copy the key → goes into `.env` as `YOUTUBE_API_KEY`

### 1.3 Reddit API (free)
1. Go to https://www.reddit.com/prefs/apps
2. Scroll to bottom → "create another app"
3. Name: "CompetitorIntelBot", Type: "script"
4. Redirect URI: http://localhost
5. Click Create → copy "client id" (under app name) and "secret"
6. → `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env`

### 1.4 Meta Ad Library API (free — optional)
1. Go to https://developers.facebook.com
2. Create app → Business type
3. Add "Marketing API" product
4. Tools → Graph API Explorer → get User Access Token
5. → `META_ACCESS_TOKEN` in `.env`
6. Find competitor page IDs at: https://www.facebook.com/ads/library

### 1.5 Gmail App Password (for email alerts)
1. Google Account → Security → 2-Step Verification (must be ON)
2. Security → App Passwords → Select app: Mail → Generate
3. Copy the 16-character password → `SMTP_PASSWORD` in `.env`

### 1.6 Slack Webhook (optional)
1. Go to https://api.slack.com/apps
2. Create App → From scratch → Pick workspace
3. Incoming Webhooks → Activate → Add New Webhook → Pick channel
4. Copy webhook URL → `SLACK_WEBHOOK_URL` in `.env`

---

## PART 2 — Configure competitors (5 minutes)

Open `config/config.yaml` and edit the competitors section:

```yaml
competitors:
  - name: "YourCompetitor"
    rss_feeds:
      - "https://theirsite.com/blog/rss.xml"    # find this on their blog
    youtube_channel_id: "UCxxxxx"                # from their YouTube URL
    reddit_keywords: ["their brand", "their product name"]
    meta_ad_page_id: "123456789"                 # optional
```

**How to find a competitor's RSS feed:**
- Most blogs: `https://theirsite.com/feed` or `/rss.xml` or `/blog/feed`
- Try visiting their blog → right-click → View Source → search "rss"

**How to find a YouTube Channel ID:**
- Visit their channel → View Source → search `"channelId"`

**That's the only config file you need to edit.** Everything else is controlled here:
- Change poll frequency: `app.poll_interval_minutes`
- Enable/disable alerts: `alerts.triggers.*`
- Change AI model: `apis.groq.model`

---

## PART 3 — Run locally to test (10 minutes)

```bash
# 1. Clone / unzip the project
cd competitor-intel

# 2. Copy and fill env file
cp .env.example .env
nano .env          # paste your API keys

# 3. Install Python deps (for local test)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Run locally
uvicorn app.api.main:app --reload

# 5. Open in browser:
#    API docs:  http://localhost:8000/docs
#    Summary:   http://localhost:8000/api/summary

# 6. Trigger a manual poll to test all agents:
curl -X POST http://localhost:8000/api/trigger-poll
```

Check logs — you should see agents running and data being saved.

---

## PART 4 — Run with Docker locally (5 minutes)

```bash
# Build and start all services
docker compose up -d --build

# Check all containers are healthy
docker compose ps

# View logs
docker compose logs -f api

# Access:
#   API:        http://localhost:8000
#   API Docs:   http://localhost:8000/docs
#   Grafana:    http://localhost:3000   (admin / your GRAFANA_ADMIN_PASSWORD)
#   MLflow:     http://localhost:5000
#   Prometheus: http://localhost:9090
```

---

## PART 5 — Deploy to AWS EC2 Free Tier (20 minutes)

### 5.1 Launch EC2 instance
1. Go to https://console.aws.amazon.com/ec2
2. Click "Launch Instance"
3. Settings:
   - **Name:** competitor-intel
   - **AMI:** Ubuntu Server 24.04 LTS (Free tier eligible)
   - **Instance type:** t2.micro (Free tier — 750 hrs/month free for 12 months)
   - **Key pair:** Create new → download `.pem` file → save it safely
   - **Security group:** Allow inbound:
     - SSH (22) — My IP only
     - HTTP (80) — Anywhere
     - HTTPS (443) — Anywhere
     - Custom TCP 3000 — Anywhere (Grafana)
     - Custom TCP 5000 — Anywhere (MLflow)
4. Launch instance

### 5.2 Connect to your EC2
```bash
# Make key read-only (required)
chmod 400 your-key.pem

# SSH in (replace with your EC2 Public IP)
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
```

### 5.3 Run setup script
```bash
# On the EC2 server:
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/competitor-intel/main/scripts/setup_ec2.sh | bash
```

Or manually:
```bash
# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git curl
sudo systemctl start docker
sudo usermod -aG docker ubuntu
# Log out and back in for group to apply

# Clone your repo
git clone https://github.com/YOUR_USERNAME/competitor-intel.git /opt/competitor-intel
cd /opt/competitor-intel

# Set up env
cp .env.example .env
nano .env    # fill in all your API keys

# Create data dirs
mkdir -p data logs

# Start everything
docker compose up -d --build
```

### 5.4 Verify deployment
```bash
# Check all containers running
docker compose ps

# Check API health
curl http://localhost:8000/health

# View logs
docker compose logs -f api

# Trigger first poll
curl -X POST http://localhost:8000/api/trigger-poll
```

### 5.5 Access your dashboards
Replace `YOUR_EC2_IP` with your actual IP:

| Service | URL | Credentials |
|---|---|---|
| API | `http://YOUR_EC2_IP:8000/docs` | none |
| Grafana | `http://YOUR_EC2_IP:3000` | admin / your password |
| MLflow | `http://YOUR_EC2_IP:5000` | none |
| Prometheus | `http://YOUR_EC2_IP:9090` | none |

---

## PART 6 — Set up CI/CD with GitHub Actions (10 minutes)

### 6.1 Push code to GitHub
```bash
# Local machine:
git init
git add .
git commit -m "Initial competitor intel agent"
git remote add origin https://github.com/YOUR_USERNAME/competitor-intel
git push -u origin main
```

### 6.2 Add GitHub Secrets
GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret name | Value |
|---|---|
| `EC2_HOST` | Your EC2 public IP |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contents of your `.pem` file |
| `GROQ_API_KEY` | Your Groq key |
| `YOUTUBE_API_KEY` | Your YouTube key |
| `REDDIT_CLIENT_ID` | Your Reddit ID |
| `REDDIT_CLIENT_SECRET` | Your Reddit secret |
| `ALERT_EMAIL_FROM` | Your Gmail |
| `ALERT_EMAIL_TO` | Where alerts go |
| `SMTP_PASSWORD` | Gmail app password |
| `GRAFANA_ADMIN_PASSWORD` | Pick a password |
| `GRAFANA_SECRET_KEY` | Any random string |

### 6.3 Deploy automatically
Now every `git push` to `main` auto-deploys to your EC2.

---

## PART 7 — Using MLflow (experiment tracking)

MLflow automatically tracks every agent run. To view:

1. Open `http://YOUR_EC2_IP:5000`
2. Click "competitor-intelligence" experiment
3. See every run with metrics:
   - `blog_posts_found` — new posts per run
   - `agent_latency_ms` — how fast each agent ran
   - `total_tokens_used` — Groq API usage
   - `avg_sentiment` — average public sentiment score
   - `eval_coverage_score` — % of sources successfully polled
   - `eval_sentiment_accuracy` — AI label accuracy
   - `eval_overall_score` — pipeline health score

**To compare runs:** Select multiple runs → Compare → see metric charts side by side.

---

## PART 8 — Using Grafana (live dashboards)

1. Open `http://YOUR_EC2_IP:3000`
2. Login: admin / your `GRAFANA_ADMIN_PASSWORD`
3. Dashboards → Browse → "Competitor Intelligence"

The pre-built dashboard shows:
- API request rate and latency in real time
- Error rate and health score
- Requests per endpoint over time
- P50 / P90 / P99 latency percentiles

**To add custom panels:**
1. Click "+" → Add panel
2. Query: `http_requests_total` (any Prometheus metric)
3. Visualisation: pick Graph, Stat, Gauge, etc.

---

## PART 9 — Evaluator scores explained

Every 3 hours (6 polls × 30 min), the evaluator runs and logs 4 scores to MLflow:

| Metric | What it means | Good score |
|---|---|---|
| `coverage_score` | % of sources that were polled successfully | > 0.9 |
| `data_freshness` | Did each competitor have activity in the last 24h? | > 0.8 |
| `sentiment_accuracy` | AI sentiment labels vs Groq spot-check | > 0.8 |
| `alert_precision` | New content was alerted promptly | > 0.9 |
| `overall_score` | Average of all above | > 0.85 |

If `overall_score` drops below 0.7, check:
- Are your API keys still valid? (`docker compose logs api`)
- Did a competitor remove their RSS feed?
- Did Reddit/YouTube API quota reset?

---

## Common commands

```bash
# View all container logs
docker compose logs -f

# View only app logs
docker compose logs -f api

# Restart just the app (after config change)
docker compose restart api

# Stop everything
docker compose down

# Update app after code change
git pull && docker compose up -d --build api

# Manual poll
curl -X POST http://localhost:8000/api/trigger-poll

# See collected data
curl http://localhost:8000/api/blog-posts | python3 -m json.tool
curl http://localhost:8000/api/sentiment

# Check database
sqlite3 data/intel.db "SELECT competitor, COUNT(*) FROM blog_posts GROUP BY competitor;"

# Backup database
cp data/intel.db data/intel_backup_$(date +%Y%m%d).db
```

---

## Adding a new competitor

Edit `config/config.yaml`, add to the `competitors` list, then:

```bash
docker compose restart api
curl -X POST http://localhost:8000/api/trigger-poll
```

No code changes, no rebuild. Done.

---

## Cost breakdown (Year 1)

| Item | Cost |
|---|---|
| AWS EC2 t2.micro | FREE (12 months) |
| Groq API | FREE (generous limits) |
| YouTube Data API | FREE (10k req/day) |
| Reddit API | FREE |
| Meta Ad Library | FREE |
| SendGrid (email) | FREE (100/day) |
| Grafana self-hosted | FREE |
| MLflow self-hosted | FREE |
| **Total Year 1** | **$0** |
| After month 12 (EC2) | ~$8/month |

**Alternative after year 1:** Migrate to Oracle Cloud Free Tier (permanent free VM, better specs than t2.micro).
