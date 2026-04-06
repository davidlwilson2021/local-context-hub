# Knowledge Base Schema

## What This Is

A personal knowledge base about **[YOUR TOPIC]**. Replace this with the domain you want this wiki to cover (e.g. your work stack, a research area, or a learning path).

## How It's Organized

- **raw/** — Unprocessed source material (articles, notes, exports, screenshots). **Do not edit these files by hand** after ingest; they are the ground truth from external sources.
- **wiki/** — The organized wiki. The AI maintains this from `raw/` and your instructions.
- **outputs/** — Generated reports, answers, briefings, and analyses grounded in the wiki and raw sources.

## Wiki Rules

- Every topic gets its own `.md` file under `wiki/`.
- Every wiki file starts with a one-paragraph summary.
- Link related topics using `[[topic-name]]` (wikilink style).
- Maintain **`wiki/INDEX.md`** listing every topic with a one-line description. Update it when topics are added or renamed.
- When new files appear in `raw/`, update or create the relevant wiki articles and cross-links.

## Compounding Loop

- Save answers and research back into `outputs/` or fold durable insights into `wiki/` so later questions build on prior work.
- Run periodic **health checks** (see below) so mistakes in outputs do not compound unchecked.

## Health Check (Run Periodically)

Ask your AI to:

1. Review all of `wiki/` for internal contradictions.
2. Flag topics mentioned but never explained.
3. List claims not clearly tied to a source in `raw/`.
4. Suggest a few new articles that would close obvious gaps.

## Optional: Automated Collection

To scrape pages into `raw/` with a CLI browser agent (e.g. agent-browser):

```bash
npm install -g agent-browser
agent-browser install
# Example workflow: open URL, extract text, save into raw/ as a new .md or .txt
```

Use this for JS-heavy pages, long scrolls, or flows that are painful to copy by hand.

## My Interests

Focus this knowledge base on:

1. **[Interest 1]** — e.g. primary domain or goal
2. **[Interest 2]** — e.g. tools, methods, or subtopics
3. **[Interest 3]** — e.g. people, projects, or questions you revisit often
4. **[Interest 4]** *(optional)*
5. **[Interest 5]** *(optional)*

---

*Keep this file simple and flat. It is the instruction manual for how the AI should treat this folder.*
