# Discord Against Humanity

A Discord bot to play **Cards Against Humanity** with your friends, right inside your server.

- Slash commands only, no privileged intent required.
- Each player gets a private channel showing their hand; the game happens on a shared `#board`.
- State is stored in [Valkey](https://valkey.io); cards come from
  [JSON Against Humanity](https://github.com/crhallberg/json-against-humanity) (6,000+ black
  and 22,000+ white cards).
- Shipped as a multi-arch container image on GHCR and a Helm chart compliant with the Kubernetes
  [`restricted` Pod Security Standard](https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted).

## How to play

| Command | Who | What it does |
|---------|-----|--------------|
| `/create` | anyone | Creates the game: a category and a `#board` channel |
| `/join` | anyone | Joins the game and opens your private channel |
| `/start [points] [winner_czar]` | player | Starts the game (first to `points`, default 5, wins); see house rules below |
| `/vote answers:<n…>` | player | Plays card(s) without the buttons, e.g. `/vote answers:2 5` |
| `/czar answer:<n>` | Card Czar | Picks the winning answer without the buttons |
| `/hand` | player | Shows your cards |
| `/score` | anyone | Shows the scoreboard |
| `/stop` | anyone | Stops the current game (back to the lobby) |
| `/leave` | player | Leaves the game |
| `/delete` | anyone | Deletes the game and its channels |
| `/reminder` | anyone | Shows the rules |

The bot follows the [official rules](https://www.cardsagainsthumanity.com/):

- A game needs **at least 3 players**. Everyone holds **10 white cards**, topped up every round.
- Each round, the **Card Czar** draws a black card and everyone else answers by **clicking cards**
  under their hand, in their private channel. Click order is answer order: the first card fills
  the first blank, the second card the second blank. A preview of the sentence is updated on each
  click, then **Play** submits it.
- On **"Draw 2, Pick 3"** cards, the players who answer draw 2 extra cards first.
- Once all answers are in, they are revealed anonymously and the Card Czar selects the best one
  with the buttons, then presses **Crown this answer**. Its author scores a point.
- The Card Czar role then passes to the next player, in join order.
- Players may join or leave at any time: late joiners play from the next round, and if the Card
  Czar leaves the round is replayed with the next player as Card Czar.

House rule: `/start winner_czar:True` makes the round winner the next Card Czar instead, as in
earlier versions of the bot.

Black cards asking for more than 3 answers (a few fan-made ones) are skipped, since no hand could
fill them.

Buttons carry their whole state in their custom IDs (round, cards picked so far): they keep working
across bot restarts and need no storage.

The bot needs the **Manage Channels** permission, plus **View Channels** and **Send Messages**.
Invite it with the `bot` and `applications.commands` scopes.

## Getting started

The whole toolchain is described in [`mise.toml`](mise.toml). [uv](https://docs.astral.sh/uv/)
is the only supported way to manage Python dependencies.

```bash
# 1. Install mise: https://mise.jdx.dev/getting-started.html
# 2. Install the tools (Python, uv, prek, Helm) and the git hooks
mise install
mise run setup
# 3. List the available tasks
mise tasks
```

Put your secrets in a git-ignored `.env` file, which mise and Docker Compose both read:

```env
DISCORD_TOKEN=your-bot-token
```

### Run locally

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:9
mise run seed       # load the card catalog (only once)
mise run run        # start the bot
```

Or run the full stack (Valkey, seeding, bot) with Docker Compose:

```bash
mise run compose:up
```

### Quality gates

Git hooks are managed by [prek](https://prek.j178.dev) (a fast `pre-commit` drop-in) and the CI
runs exactly the same hooks:

| Gate | Tool | When |
|------|------|------|
| Lint & format | [Ruff](https://docs.astral.sh/ruff/) | commit |
| Types | [ty](https://docs.astral.sh/ty/) | commit |
| Hexagonal layers | [import-linter](https://import-linter.readthedocs.io) | commit |
| Lockfile in sync | `uv lock` (uv-pre-commit) | commit |
| Dockerfile | [hadolint](https://github.com/hadolint/hadolint) | commit |
| GitHub workflows | [actionlint](https://github.com/rhysd/actionlint) | commit |
| Helm chart | `helm lint --strict` | commit |
| Secrets | [gitleaks](https://github.com/gitleaks/gitleaks) | commit |
| Unit tests | pytest | push |
| Integration tests | pytest + [Testcontainers](https://testcontainers.com) (Docker) | CI |

`mise run check` runs every hook on the whole repository.

## Architecture

The code follows a hexagonal (ports & adapters) architecture. The dependency rule is enforced
by import-linter: inner layers never import outer ones, the core never imports `discord` or
`valkey`, and adapters do not depend on each other.

```
src/discord_against_humanity/
├── domain/          Pure game rules: Game aggregate, cards, errors. No I/O.
├── application/
│   ├── ports.py     Interfaces needed by the core: GameRepository, CardDeck,
│   │                CardCatalog, GameNotifier
│   ├── service.py   Use cases: create, join, start, vote, pick winner…
│   └── seeding.py   Use case: load the card catalog
├── adapters/
│   ├── discord/     Slash commands (driving) and notifications (driven)
│   ├── valkey/      Game repository and card store
│   ├── memory.py    In-memory implementations (tests)
│   └── cah_json.py  Reader for JSON Against Humanity exports
├── config.py        Settings from environment variables
└── main.py          Composition root and CLI
```

The game is event-driven: the last answer opens the judging phase, and the Card Czar's pick scores and
starts the next round. Every use case runs under a per-guild lock, so the bot must run as
**a single process** (which a Discord bot token requires anyway).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | Bot token (required to run the bot) |
| `VALKEY_HOST` | `localhost` | Valkey host |
| `VALKEY_PORT` | `6379` | Valkey port |
| `VALKEY_DB` | `0` | Valkey database number |
| `VALKEY_PASSWORD` | — | Valkey password, if any |
| `LOG_LEVEL` | `INFO` | Python log level |
| `CARDS_SOURCE` | public catalog | Path or URL used by `seed` when no argument is given |

### Card catalog

```bash
discord-against-humanity seed                       # full public catalog
discord-against-humanity seed --official-only       # official packs only
discord-against-humanity seed ./my-cards.json       # local file or any URL
discord-against-humanity seed --force               # replace the existing catalog
```

The command understands the compact, full and legacy formats from
[crhallberg.com/cah](https://crhallberg.com/cah/), and does nothing if cards are already loaded.
Card IDs are derived from the card text, so seeding is idempotent. Catalogs seeded by earlier
versions of the bot are still compatible.

## Deployment

### Container image

Each push to `master` publishes `ghcr.io/wihrt/discord_against_humanity` (`linux/amd64` and
`linux/arm64`, with SBOM and provenance), tagged `latest` and `sha-<commit>`. Pushing a `vX.Y.Z`
git tag also publishes `X.Y.Z` and `X.Y`. Pull requests build the image without pushing it.

The image runs as UID `10001`, contains neither uv nor the sources, and works with a read-only root
filesystem and no Linux capabilities.

### Kubernetes (Helm)

```bash
kubectl create namespace cah
kubectl label namespace cah pod-security.kubernetes.io/enforce=restricted
kubectl -n cah create secret generic discord-bot --from-literal=DISCORD_TOKEN=your-token

helm install cah helm/discord-against-humanity -n cah \
  --set existingSecret=discord-bot \
  --set valkey.host=valkey.example.svc.cluster.local
```

A post-install/post-upgrade Job loads the card catalog (`seed.enabled`). The CI checks that the
chart is admitted in a namespace enforcing the `restricted` profile.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `image.repository` | `ghcr.io/wihrt/discord_against_humanity` | Image |
| `image.tag` | chart `appVersion` | Image tag |
| `image.digest` | `""` | Optional immutable digest |
| `existingSecret` | `""` | Secret holding `DISCORD_TOKEN` |
| `discordToken` | `""` | Token, used only without `existingSecret` |
| `valkey.host` / `valkey.port` / `valkey.db` | `valkey` / `6379` / `0` | Valkey server |
| `valkey.passwordSecret.name` / `.key` | `""` / `password` | Optional Valkey password Secret |
| `logLevel` | `INFO` | Log level |
| `seed.enabled` | `true` | Run the seed Job |
| `seed.source` | `""` | Card source (path or URL), defaults to the public catalog |
| `seed.officialOnly` | `false` | Only load official packs |
| `podSecurityContext` / `securityContext` | restricted | Security contexts |
| `resources` | 50m / 96Mi, limit 256Mi | Bot resources |

## Dependency updates

[Renovate](https://docs.renovatebot.com) ([`renovate.json`](renovate.json)) keeps everything up to
date: Python packages (`uv.lock`), mise tools, prek hooks, Docker images (pinned by digest), GitHub
Actions (pinned by commit SHA) and the Valkey image used in tests. It runs on Monday mornings
(Europe/Paris), groups related updates and merges low-risk ones once the CI is green. Runtime
dependencies and new Python minor versions always wait for a human review.

## License

No license has been chosen for this project yet.

Card texts come from [JSON Against Humanity](https://github.com/crhallberg/json-against-humanity),
based on Cards Against Humanity, which is distributed under a
[Creative Commons BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license.
