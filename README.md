# Second Brain (flat-file knowledge base)

This repo scaffolds a **personal knowledge base**: three folders, one schema file, no database.

## Layout

```
my-knowledge-base/
  CLAUDE.md    # schema / rules for your AI (edit YOUR TOPIC and interests)
  raw/         # source material — paste articles, notes, exports here
  wiki/        # organized wiki — maintained by your AI from raw/ + schema
  outputs/     # answers, reports, research outputs
```

1. Put sources in `raw/`.
2. Edit `CLAUDE.md` with your topic and wiki rules.
3. Point your AI at `my-knowledge-base/` and ask it to compile or update `wiki/` from `raw/` following `CLAUDE.md`, starting with `wiki/INDEX.md`.

Optional: use [agent-browser](https://github.com/vercel-labs/agent-browser) (or similar) to scrape URLs into `raw/`. Run periodic wiki health checks as described in `CLAUDE.md`.
