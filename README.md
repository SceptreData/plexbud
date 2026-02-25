# plexbud

Darn it all to heck- the plex is full. AGAIN. What to delete? What to keep?
Is anyone watching any of this junk? Worse, you're probably using hardlinks-
because you thought you were SMART and of course its better to have files in
multiple places what could possibly go wrong.


plexbud is a tool to help in these trying times. What's taking up space? Where
is it?

Plexbud answers two questions:

1. **What's eating all my space?**
2. **How do I nuke it from orbit?**
3. **BAH HARDLINKS**

It talks to Sonarr, Radarr, Tautulli, and qBittorrent so you don't have to
manually cross-reference four different UIs.

## What it does

**Stats** — See what's big, what's unwatched, and what's been collecting dust since 2019:

```
plexbud stats tv --sort size --min-size 20GiB
plexbud stats movies --unwatched 90d --limit 20
plexbud                                          # both at once, with disk usage
```

**Delete** — Remove a show or movie from *everywhere* in one shot (Sonarr/Radarr, qBittorrent, filesystem):

```
plexbud delete tv "that show nobody watches"     # dry-run by default, because mistakes
plexbud delete tv "that show" --apply             # actually do it
plexbud delete tv                                 # interactive TUI for the indecisive
```

Using the delete command removes media completely. It finds all the hardlinks, stops all the torrents, deletes the .nzb's and removes and unmonitors the show/movie from Radarr/Sonarr.

It's _hardcore_ - and because of that,deletion is dry-run by default. It warns you about active streams and recently-added items, or if someone has watched that show in the past 30 days.

## Install


```bash
# Requires Python 3.13+ -- old stuff that works with minimal fuss on synology
pip install .
```

### Docker (Synology)

```bash
docker compose run --rm plexbud stats tv
docker compose run --rm plexbud delete movie
```

The compose file mounts your media volume read-only and your config file. See `docker-compose.yml`.

## Config

Create `~/.config/plexbud/config.toml`:

```toml
[tautulli]
url = "http://localhost:8181"
api_key = "your-tautulli-api-key"
tv_section_id = 1
movie_section_id = 2

[sonarr]
url = "http://localhost:8989"
api_key = "your-sonarr-api-key"

[radarr]
url = "http://localhost:7878"
api_key = "your-radarr-api-key"

[qbittorrent]
url = "http://localhost:8080"
username = "admin"
password = "adminadmin"

[paths]
media_movies = "/volume1/data/media/movies"
media_tv = "/volume1/data/media/tv"
torrents_root = "/volume1/data/torrents"
usenet_complete = "/volume1/data/usenet/complete"
```

**Required vs optional**

- The config file itself has to exist—no file, no plexbud (it'll error out and exit). Everything *in* the file is optional: skip a section and that service gets empty defaults; when you run a command that needs it, you'll get the usual connection or API failure instead of a helpful "you forgot to configure X" message.
- **By command:**
  - **`stats tv`** — needs `[sonarr]`, `[tautulli]`, and `[paths]` with at least `media_tv`.
  - **`stats movies`** — same idea but `[radarr]` and `media_movies`.
  - **`delete`** — needs the right arr + Tautulli for that media type, `[qbittorrent]`, and `[paths]` (media paths plus `torrents_root` / `usenet_complete` if you use them).

Bottom line: you can start with a minimal config (e.g. only sonarr, tautulli, and `media_tv`) and run `stats tv`; add the rest when you need the other commands.

Adjust URLs and paths to match your setup. If you're on Synology, the `/volume1/data/...` paths probably look familiar.

## CLI reference

```
plexbud                          Show disk usage + stats for everything
plexbud stats tv                 TV stats, sorted by size
plexbud stats movies             Movie stats, sorted by size
plexbud stats tv -s lastwatched  Sort by last watched (oldest first)
plexbud stats tv -s watched30d   Sort by recent watch count
plexbud stats tv -n 10           Top 10 only
plexbud stats tv --min-size 50GiB    Big boys only
plexbud stats tv --hide-added 30d    Hide stuff added recently
plexbud stats tv --unwatched 90d     Unwatched for 90+ days
plexbud stats tv --plain             TSV output for piping
plexbud delete                	Interactive TUI
plexbud delete tv "breaking bad" Dry-run deletion plan
plexbud delete tv "breaking bad" --apply   Actually delete
plexbud delete tv "breaking bad" --apply -y   Skip confirmation (brave)
plexbud delete movie "the room"  You know what you did
```

## How it works

Three layers, no magic:

```
Commands (CLI/TUI)  →  Services (logic)  →  Clients (HTTP)
```

- **Clients** wrap each service's API (Sonarr, Radarr, Tautulli, qBittorrent)
- **Services** do the cross-referencing — matching Sonarr's tvdbId to Tautulli's watch history, scanning for hardlinks to calculate *actual* freeable space, building deletion plans
- **Commands** handle the CLI flags and pretty-printing

The hardlink-aware space calculation is the spicy part. If a file has hardlinks outside the deletion set, plexbud knows you won't actually free that space and reports accordingly. No more "I deleted 200GB but got 0 bytes back" surprises.

## Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/ -v              # tests
ruff check src/               # lint
ruff format src/ tests/       # format
mypy src/                     # type check (strict)
```

Mock mode lets you poke around without real services:

```bash
PLEXBUD_MOCK=1 plexbud stats tv
```

## Dependencies

mostly stuff to look pretty

| Package | Why |
|---------|-----|
| typer | CLI framework |
| rich | Pretty tables and progress bars |
| httpx | HTTP client |
| textual | Interactive TUI |

## License

MIT 2026