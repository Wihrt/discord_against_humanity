# Discord Against Humanity

A Discord bot that lets you play **Cards Against Humanity** with your friends directly inside a Discord server.

## Features

- **Slash commands** — all interactions use Discord's native slash commands (`/create`, `/join`, `/vote`, …).
- **Async** — built on top of [discord.py](https://discordpy.readthedocs.io/) 2.x and [Motor](https://motor.readthedocs.io/) for fully asynchronous I/O.
- **MongoDB** persistence — game state, players, and cards are stored in MongoDB 8.
- **Containerised** — ships with an optimised, multi-stage Dockerfile (non-root, bytecode-compiled).
- **Kubernetes-ready** — includes a Helm chart for one-command deployments.

## How to Play

| Step | Command | Description |
|------|---------|-------------|
| 1 | `/create` | Create a new game in the current server |
| 2 | `/join` | Join the game (each player gets a private channel) |
| 3 | `/start` | Start the game (optional: `/start points:10`) |
| 4 | `/vote` | Players pick white cards via `/vote answers:1 3` |
| 5 | `/tsar` | The Tsar selects the winning answer via `/tsar answer:2` |
| 6 | `/score` | View the scoreboard at any time |
| 7 | `/stop` | Stop the game early |
| 8 | `/leave` | Leave the game |
| 9 | `/delete` | Delete the game and clean up channels |

Use `/reminder` to display the game rules at any time.

## Requirements

- Python ≥ 3.13
- MongoDB ≥ 8
- A [Discord Bot Token](https://discord.com/developers/applications)
- [uv](https://docs.astral.sh/uv/) (for local development)

## Local Development

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/Wihrt/discord_against_humanity.git
cd discord_against_humanity
uv sync          # installs all deps including dev tools

# Run linter, tests and type checker
uv run ruff check src/ tests/
uv run pytest
uv run mypy src/

# Start the bot (requires DISCORD_TOKEN and a running MongoDB)
export DISCORD_TOKEN="your-token-here"
export MONGO_HOST="localhost"
export MONGO_PORT="27017"
uv run discord-against-humanity
```

## Deploy with Docker Compose

1. Create a `.env` file:

   ```env
   DISCORD_TOKEN=your-bot-token-here
   ```

2. Start the stack:

   ```bash
   docker compose up -d
   ```

   This starts:
   - **bot** — the Discord bot (Python 3.13, non-root)
   - **mongo** — MongoDB 8

3. Stop:

   ```bash
   docker compose down
   ```

## Deploy with Helm (Kubernetes)

### Using an existing Secret

Create a Kubernetes Secret containing your Discord token before installing the chart:

```bash
kubectl create secret generic discord-bot-token \
  --from-literal=DISCORD_TOKEN=your-token-here
```

Then install the chart referencing that secret:

```bash
helm install my-bot helm/discord-against-humanity \
  --set existingSecret=discord-bot-token \
  --set mongodb.host=my-mongo-service
```

### Letting the chart create the Secret

```bash
helm install my-bot helm/discord-against-humanity \
  --set discordToken=your-token-here \
  --set mongodb.host=my-mongo-service
```

### Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Container image | `ghcr.io/wihrt/discord_against_humanity` |
| `image.tag` | Image tag | `latest` |
| `existingSecret` | Name of a pre-existing Secret with `DISCORD_TOKEN` | `""` |
| `discordToken` | Bot token (used only when `existingSecret` is empty) | `""` |
| `mongodb.host` | MongoDB hostname | `mongo` |
| `mongodb.port` | MongoDB port | `27017` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |
| `resources.limits.cpu` | CPU limit | `200m` |
| `resources.limits.memory` | Memory limit | `256Mi` |

## CI / CD

| Workflow | Trigger | Steps |
|----------|---------|-------|
| **PR** | Pull request → `main` | Ruff → Pytest → mypy → Docker build (no push) |
| **Main** | Push to `main` | Ruff → Pytest → Docker build & push (`ghcr.io`, tagged with short SHA + `latest`) |
| **Tag** | Manual dispatch | Docker build & push tagged with the given version |

## Project Structure

```
.
├── src/discord_against_humanity/   # Bot source code
│   ├── bot.py                      # Entry point & bot setup
│   ├── commands/cah.py             # Slash command Cog
│   ├── checks/game_checks.py      # Pre-command validation
│   ├── domain/                     # Domain models (game, player, cards)
│   ├── infrastructure/mongo.py     # MongoDB document base class
│   └── utils/                      # Embed builder & debug decorator
├── tests/                          # Unit tests (pytest)
├── helm/                           # Helm chart
├── Dockerfile                      # Multi-stage, non-root, uv-based
├── docker-compose.yml              # Local stack (bot + MongoDB 8)
└── pyproject.toml                  # Project & tool configuration (uv)
```

## License

This project is open source. See the repository for details.