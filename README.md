# Technical Challenge Reviewer

A full-stack Dockerized system that receives a GitHub user's repository challenge response and evaluates it via AI.

- **PHP 8.4 + Symfony 7.3** - Main API & UI, persistence, Messenger (Doctrine transport) for reliable async processing
- **Python 3.12 + FastAPI** - Evaluator microservice, clones repo, LangChain with dual LLM (Groq primary + Gemini fallback)
- **Postgres 17** - Stores challenges, submissions, evaluation results, and Messenger messages (no RabbitMQ needed)
- **Nginx** - Reverse proxy
- **Twig UI** with polling status page

## Architecture

```
User -> Nginx:8080 -> PHP-FPM Symfony
           |
           | Persist PENDING + dispatch EvaluateSubmissionMessage -> Doctrine transport (postgres messenger_messages table)
           v
     php-worker (messenger:consume async)
           |
           | HTTP POST http://python-evaluator:8000/evaluate {submissionId, repoUrl, challengeText, callbackUrl, token}
           v
      Python FastAPI: 202 Accepted + BackgroundTask (lifespan starts replay cron)
            - git clone --depth 1
            - file_collector: walk ignoring node_modules, vendor, .git etc, collect tree + truncated contents (25k chars)
            - prompts: build_evaluation_prompt
             - llm_provider: try Groq llama-3.3-70b-versatile, on failure Gemini gemini-2.0-flash-lite via LangChain, JsonOutputParser, fallback heuristic if no keys
            - result {approved: bool, summary, improvements[], reasoning}
            - callback POST to Symfony /api/internal/evaluation-result with tenacity retry 5x (2s,4s,8s,16s,30s = 60s window)
            -> On final failure: persisted to /tmp/failed_callbacks.jsonl (DLQ)
            -> Cron: callback_replayer.py loop every 60s (asyncio.to_thread) replays DLQ, atomic rewrite, clears on success
            -> Admin: GET /admin/replay-status, POST /admin/replay-failed-callbacks
            v
      Symfony CallbackController validates X-Internal-Token, updates submission APPROVED/REJECTED + json result
           ^
           | Polling every 3s
     Browser: /submissions/{id} status page
```

### Why No RabbitMQ?

Symfony Messenger with Doctrine transport provides:

- **Durability**: Messages persisted in Postgres `messenger_messages` table
- **Retries**: Configurable `retry_strategy` (3x, delay 2s * multiplier 2, max 10s)
- **Failed queue**: `failed` transport `doctrine://default?queue_name=failed`, inspect via `messenger:failed:show`, retry via `messenger:failed:retry`
- **Zero ops overhead**: Reuses existing Postgres, no extra container
- **Swappable**: Change `MESSENGER_TRANSPORT_DSN` to `amqp://` to use RabbitMQ without code change

For high throughput (>1k msg/min) RabbitMQ would give better performance, but for this use case (long LLM tasks ~30-60s, low volume) Doctrine is sufficient.

**Failure handling**:

1. PHP -> Python HTTP fails (Symfony → Python down): Messenger retries 3x (2s*2 multiplier max 10s), then moves to `failed` transport `doctrine://default?queue_name=failed`. Inspect via `messenger:failed:show`, retry via `messenger:failed:retry`. Guarantees no message lost if Python is down.
2. Python -> PHP callback fails (Symfony down during callback): Tenacity retries 5x (2s,4s,8s,16s,30s = 60s window) on `RequestError` + `HTTPStatusError`. On final failure, persisted to `/tmp/failed_callbacks.jsonl` (DLQ) via `_log_failed_callback`. Cron `callback_replayer.py` started in FastAPI `lifespan` every 60s (`asyncio.to_thread` + atomic rewrite) auto-replays DLQ when Symfony recovers. Proven: 70s outage → file created, submission `processing`, nginx up → replay `1/1 recovered`, file cleared, `approved`. Admin endpoints: `GET /admin/replay-status`, `POST /admin/replay-failed-callbacks` for manual trigger.
3. Both down: Messenger messages stay in Postgres, callbacks stay in DLQ file (survives container restart if volume mounted), both processed on restart via cron.
4. Manual retry: `POST /api/submissions/{id}/retry` re-dispatches (re-clones + re-evaluates) and `POST /admin/replay-failed-callbacks` replays only callback without re-evaluating.

## Quick Start

### Prerequisites

- Docker & Docker Compose v5+
- Free LLM API keys (optional for testing, but required for real AI evaluation):
  - Groq: https://console.groq.com/keys (generous free tier, very fast)
  - Gemini: https://aistudio.google.com/app/apikey (free quota)

### Setup

```bash
# Clone and enter
cd technical_challenge_reviewer

# Copy env and set your keys
cp .env.example .env
# Edit .env and set:
# GROQ_API_KEY=gsk_...
# GEMINI_API_KEY=...
# CALLBACK_TOKEN=some_random_secret

# Build and up
docker compose build
docker compose up -d

# Wait for DB healthy
docker compose ps

# Install Symfony deps (if not already)
docker compose exec php composer install

# Run migrations
docker compose exec php php bin/console doctrine:migrations:migrate --no-interaction
docker compose exec php php bin/console messenger:setup-transports --no-interaction

# Create test DB for tests
docker compose exec php php bin/console doctrine:database:create --env=test --if-not-exists
docker compose exec php php bin/console doctrine:migrations:migrate --env=test --no-interaction
docker compose exec php php bin/console messenger:setup-transports --env=test
```

Services:

- Symfony UI/API: http://localhost:8080
- Python Evaluator Docs: http://localhost:8001/docs
- Postgres: localhost:5432 (user app, pass app, db challenge_reviewer)

### Usage

#### Via UI

1. Go to http://localhost:8080
2. Create a challenge: "New Challenge" -> Title + Description (requirements that will be sent to AI)
3. Submit: "New Submission" -> Your name, GitHub public repo URL, select challenge or custom text
4. Watch status page polling every 3s. After 30-60s, shows Approved/Rejected + improvements.

#### Via API

```bash
# List challenges
curl http://localhost:8080/api/challenges

# Create challenge
curl -X POST http://localhost:8080/api/challenges -H "Content-Type: application/json" \
  -d '{"title":"TODO API","description":"Build REST API with Symfony, CRUD todos, Doctrine, validation, tests."}'

# Submit
curl -X POST http://localhost:8080/api/submissions -H "Content-Type: application/json" \
  -d '{
    "userName":"alice",
    "githubRepoUrl":"https://github.com/octocat/Hello-World",
    "challengeId":"<uuid-from-previous>"
  }'

# Or custom challenge text
curl -X POST http://localhost:8080/api/submissions -H "Content-Type: application/json" \
  -d '{
    "userName":"bob",
    "githubRepoUrl":"https://github.com/user/repo",
    "customChallengeText":"Build a TODO API..."
  }'

# Check status
curl http://localhost:8080/api/submissions/<id>

# Retry if failed
curl -X POST http://localhost:8080/api/submissions/<id>/retry
```

### Python Evaluator API

```bash
# Health
curl http://localhost:8001/health
# {"status":"ok","llm_provider":"groq","groq_configured":true,"gemini_configured":false}

# DLQ status & manual replay (cron auto-replays every 60s)
curl http://localhost:8001/admin/replay-status
# {"failed_callbacks":0,"path":"/tmp/failed_callbacks.jsonl","replay_interval":60}
curl -X POST http://localhost:8001/admin/replay-failed-callbacks
# {"total":1,"replayed":1,"still_failing":0}

# Direct evaluate (webhook payload from Symfony)
curl -X POST http://localhost:8001/evaluate -H "Content-Type: application/json" \
  -d '{
    "submissionId":"test-123",
    "githubRepoUrl":"https://github.com/octocat/Hello-World",
    "challengeText":"Build TODO API...",
    "callbackUrl":"http://nginx/api/internal/evaluation-result",
    "callbackToken":"s3cr3t_shared_token_change_me"
  }'
```

Response 202 Accepted, background task starts. Callback retries 5x then DLQ + cron guarantees delivery.

## Entities

### Challenge
- `id: uuid v7`
- `title: string 255`
- `description: text` (requirements)
- `createdAt`

### Submission
- `id: uuid v7`
- `userName: string`
- `githubRepoUrl: string 500` (validated contains github.com)
- `challenge: ManyToOne nullable`
- `challengeSnapshot: text` (copy of challenge description at submission time)
- `status: enum PENDING, PROCESSING, APPROVED, REJECTED, FAILED`
- `approved: bool|null`
- `evaluationResult: json {approved, summary, improvements[], reasoning, raw, evaluatedAt}`
- `processingLogs: text nullable`
- `createdAt, updatedAt`

## Testing

### Symfony (PHPUnit)

```bash
docker compose exec php php bin/phpunit --testdox           # All 35 tests
docker compose exec php php bin/phpunit tests/Unit --testdox
docker compose exec php php bin/phpunit tests/Functional --testdox
```

Coverage:

- Enum SubmissionStatus (label, isFinal)
- Entity Challenge, Submission (create, relations, status transitions, toArray)
- Service EvaluationWebhookService (success, error status, payload structure, MockHttpClient)
- Controller Submission (home, new form, api list/create, validation, invalid github url, show, retry)
- Controller Challenge (new form, list, create)
- Controller InternalCallback (health, token auth, approved/rejected update, missing fields)
- MessageHandler EvaluationRequestHandler (updates status, throws on failure, handles non-existent)

### Python (Pytest)

```bash
docker compose exec python-evaluator pytest -v
# 25 tests
```

Coverage:

- file_collector: ignore logic, relevant file check, simple collection, truncation
- repo_cloner: url validation, invalid clone, success clone (octocat/Hello-World)
- llm_provider: extract JSON direct, with markdown fence, with extra text, normalize, no-keys fallback
- evaluator: no-keys heuristic, empty repo
- main: root, health, evaluate accepts, invalid challenge text
- callback: success, failure retries, payload structure
- callback_replayer: empty no file, success clears file, keeps failed (new cron DLQ logic)

### E2E Manual Test

```bash
# Submit a real repo and watch logs
docker compose logs -f php-worker
docker compose logs -f python-evaluator
# In another terminal:
curl -X POST http://localhost:8080/api/submissions -H "Content-Type: application/json" \
  -d '{"userName":"e2e","githubRepoUrl":"https://github.com/octocat/Hello-World","customChallengeText":"Test challenge that requires README and some code"}'
# Check status after ~10s
curl http://localhost:8080/api/submissions/<id> | jq
```

## Environment Variables

Root `.env` and `symfony/.env` share:

```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
DATABASE_URL=postgresql://app:app@database:5432/challenge_reviewer?serverVersion=17&charset=utf8
MESSENGER_TRANSPORT_DSN=doctrine://default?queue_name=async
APP_SECRET
PYTHON_EVALUATOR_URL=http://python-evaluator:8000
SYMFONY_INTERNAL_CALLBACK_URL=http://nginx/api/internal/evaluation-result (internal docker hostname)
CALLBACK_TOKEN=shared secret for webhook auth
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
LLM_PROVIDER=auto|groq|gemini
```

## Project Structure

```
.
├── docker-compose.yml
├── nginx/default.conf
├── symfony/ (Symfony 7.3 app)
│   ├── src/Entity/{Challenge,Submission}.php
│   ├── src/Enum/SubmissionStatus.php
│   ├── src/Message/EvaluateSubmissionMessage.php
│   ├── src/MessageHandler/EvaluationRequestHandler.php
│   ├── src/Service/EvaluationWebhookService.php
│   ├── src/Controller/{Submission,Challenge,InternalCallback}Controller.php
│   ├── templates/submission/{home,new,show}.html.twig
│   ├── migrations/
│   └── tests/
├── python-service/
│   ├── app/
│   │   ├── main.py (FastAPI + lifespan cron for DLQ replay, admin endpoints)
│   │   ├── config.py (Groq/Gemini only + failed_callbacks_path + replay interval)
│   │   ├── models.py
│   │   ├── repo_cloner.py
│   │   ├── file_collector.py
│   │   ├── prompts.py
│   │   ├── llm_provider.py (Groq+Gemini fallback)
│   │   ├── evaluator.py
│   │   ├── symfony_client.py (tenacity retry + DLQ logging)
│   │   └── callback_replayer.py (new: replay_failed_callbacks + replay_loop every 60s)
│   └── tests/
│       └── test_callback_replayer.py (DLQ unit tests)
└── README.md
```

## LLM Prompting

Prompt in `prompts.py`:

```
You are a senior reviewer...
Challenge: {challenge_text}
File Tree: {tree}
File Contents: {contents}
Return JSON: {approved, summary, improvements[], reasoning}
```

- System prompt warns to treat file contents as data, not instructions (prompt injection mitigation)
- Output constrained to valid JSON, parser extracts from markdown fences if needed
- `normalize_evaluation_result` ensures bool approved, summary, improvements list

Dual provider logic:

1. If `LLM_PROVIDER=groq` -> only Groq
2. If `gemini` -> only Gemini
3. If `auto` (default) -> try Groq, on exception try Gemini, if both fail return heuristic fallback (approved false, message about missing keys) so e2e works without keys for testing.

## Security & Limitations

- Only public GitHub repos (no PAT), shallow clone `--depth 1`, timeout 60s, size limit 100KB per file, total 25k chars for LLM context
- No code execution, only static analysis
- Callback protected by `X-Internal-Token` header, must match `CALLBACK_TOKEN`
- File collection ignores `.git, node_modules, vendor, __pycache__, etc`
- For production: add rate limiting, add GitHub PAT support for private repos, use Redis cache for evaluations, add auth for API, use HTTPS, set strong APP_SECRET and CALLBACK_TOKEN

## Future Improvements

- Add Symfony Messenger retry with dead-letter queue UI
- Add pagination & filtering for submissions
- Add webhook signature HMAC instead of simple token
- Support OpenRouter for more free models
- Add evaluation history diff
- Add GitHub App integration to auto-evaluate PRs

## License

MIT - for technical challenge demo.
