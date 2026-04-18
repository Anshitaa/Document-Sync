# Docu-Sync

> **The problem:** Developers ship UI updates constantly — and almost never update their documentation to match. Screenshots go stale, changelogs miss visual changes, and README files drift further from reality with every sprint.
>
> **The solution:** Docu-Sync watches your UI changes, understands them using vision AI, and automatically opens a GitHub Pull Request with updated documentation. No manual writing. No stale screenshots.

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)]()

---

## How It Works

Upload a before and after screenshot. Docu-Sync runs a four-stage pipeline:

```
┌──────────────────────────────────────────────────────────────────┐
│                     Docu-Sync Pipeline                           │
└──────────────────────────────────────────────────────────────────┘

 [Before Screenshot]       [After Screenshot]
        │                         │
        └────────────┬────────────┘
                     ▼
        ┌────────────────────────┐
        │   Stage 1: Detection   │
        │  ┌──────────────────┐  │
        │  │  SSIM (OpenCV)   │──┼──▶ similarity score, bounding boxes
        │  └──────────────────┘  │
        │  ┌──────────────────┐  │
        │  │  Gemini Vision   │──┼──▶ semantic_summary, changed_elements,
        │  │  (Multimodal)    │  │    change_type, severity
        │  └──────────────────┘  │
        └────────────────────────┘
                     │ change_summary
                     ▼
        ┌────────────────────────┐
        │   Stage 2: RAG         │
        │  ┌──────────────────┐  │
        │  │  Chunk README    │──┼──▶ N markdown sections
        │  └──────────────────┘  │
        │  ┌──────────────────┐  │
        │  │  Embed + Retrieve│──┼──▶ top-3 relevant sections
        │  │ (text-embed-004) │  │    (by cosine similarity)
        │  └──────────────────┘  │
        └────────────────────────┘
                     │ relevant_context
                     ▼
        ┌────────────────────────┐
        │   Stage 3: Doc Gen     │
        │  ┌──────────────────┐  │
        │  │ Gemini 1.5 Flash │──┼──▶ documentation, confidence (0–1),
        │  │  (Structured)    │  │    reasoning
        │  └──────────────────┘  │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Stage 4: GitHub PR    │
        │  ┌──────────────────┐  │
        │  │    PyGithub      │──┼──▶ Pull Request URL
        │  └──────────────────┘  │
        └────────────────────────┘
```

---

## Features

- **Dual-layer change detection** — SSIM gives pixel-level accuracy; Gemini Vision gives semantic understanding of *what* changed and *why it matters*
- **RAG-powered documentation** — retrieves the most relevant section of your existing README before writing, rather than blindly truncating
- **Confidence scoring** — every generated doc update comes with a 0–1 confidence score and a reasoning explanation
- **GitHub automation** — creates a new branch and opens a PR with the updated README automatically
- **One-click full pipeline** — web UI chains all four stages in a single click
- **Eval suite** — `eval.py` scores pipeline output quality across 11 dimensions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask |
| Change Detection | OpenCV, scikit-image (SSIM) |
| Vision AI | Google Gemini 1.5 Flash (multimodal) |
| Embeddings | Google text-embedding-004 |
| Documentation AI | Google Gemini 1.5 Flash (structured JSON output) |
| Version Control | PyGithub |
| Deployment | Gunicorn, Docker, docker-compose |

---

## Design Decisions & Tradeoffs

### Why SSIM + Vision instead of just one?

SSIM (Structural Similarity Index) is fast, deterministic, and gives precise pixel-level bounding boxes — useful for knowing *where* changes are. But it cannot tell you *what* changed semantically: it treats a button color change and a layout restructure as the same "pixel delta."

Gemini Vision fills that gap by understanding the screenshots as a UI analyst would — naming specific elements, categorising the change type, and judging severity. Combining both gives you the best of each: precise numeric grounding from SSIM and human-readable semantic understanding from the model.

**Tradeoff:** Adding the vision call increases latency (~1–2s) and costs one Gemini API request per detection. For high-volume use this would need caching or batching.

### Why RAG instead of just passing the README?

The naive approach (`readme[:500]`) always feeds the same boilerplate intro text regardless of what changed. If a navigation bar was updated, you want the model to see the *UI Components* or *Navigation* section of your README — not the project description.

RAG solves this: it chunks the README by markdown header, embeds each chunk using `text-embedding-004`, and retrieves the top-3 most semantically relevant sections using cosine similarity. The model then generates documentation grounded in the *right* context.

**Tradeoff:** RAG requires two additional embedding API calls per generation request. For very short READMEs (<300 chars), it falls back to direct inclusion automatically.

### Why structured JSON output instead of free text?

Asking the model to return free text produces inconsistent, hard-to-parse results. By prompting for a strict JSON schema (`documentation`, `confidence`, `reasoning`) and using a robust parser with markdown-fence stripping, the API response is always machine-readable and the UI can render each field independently.

**Tradeoff:** JSON prompting can occasionally produce malformed output. The client handles this with a graceful fallback that returns the raw text rather than crashing.

---

## Installation

### Prerequisites
- Python 3.8+
- Google Gemini API key — [get one free](https://makersuite.google.com/app/apikey)
- GitHub Personal Access Token

### Setup

```bash
# 1. Clone
git clone https://github.com/Anshitaa/DocumentSync.git
cd DocumentSync/services/api

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run
python app.py
```

Open [http://localhost:8080](http://localhost:8080) — or use Docker:

```bash
cd DocumentSync
docker compose up
```

---

## Configuration

```bash
# services/api/.env

GEMINI_API_KEY=your_gemini_api_key_here

GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=username/repository
GITHUB_REPO_OWNER=username
GITHUB_REPO_NAME=repository
```

---

## API Reference

### `GET /health`
Health check. Returns `{"status": "healthy"}`.

### `POST /detect-change`
Detects visual and semantic changes between two screenshots.

**Request:** `multipart/form-data` with `old_image` and `new_image` files.

**Response:**
```json
{
  "success": true,
  "ssim": 0.8542,
  "boxes": [{"x": 100, "y": 200, "width": 80, "height": 30, "area": 2400}],
  "ssim_summary": "Detected minor changes (SSIM: 0.8542). Found 1 changed region(s).",
  "semantic_summary": "The submit button color changed from blue to green and the label updated to 'Continue'.",
  "changed_elements": ["Submit button color changed from blue to green", "Button label changed from 'Submit' to 'Continue'"],
  "change_type": "color",
  "severity": "minor",
  "summary": "The submit button color changed from blue to green..."
}
```

### `POST /generate-update`
Generates structured documentation for a detected change.

**Request:**
```json
{
  "change_summary": "Submit button color changed from blue to green",
  "current_readme": "# MyApp\n## UI Components\n..."
}
```

**Response:**
```json
{
  "success": true,
  "documentation": "The submit button has been updated to green to improve visual accessibility...",
  "confidence": 0.91,
  "reasoning": "The change is clearly a colour update with high specificity...",
  "rag_headings": ["UI Components"],
  "rag_chunks_used": 2
}
```

### `POST /create-pr`
Creates a GitHub branch and Pull Request with updated documentation.

**Request:**
```json
{
  "new_text": "Updated documentation text",
  "branch": "docu-sync/auto-update"
}
```

**Response:**
```json
{
  "success": true,
  "pr_url": "https://github.com/Anshitaa/DocumentSync/pull/1",
  "pr_number": 1,
  "branch": "docu-sync/auto-update"
}
```

---

## Running the Eval Suite

```bash
cd services/api
python eval.py

# Verbose (shows full API responses):
python eval.py --verbose

# Save results to JSON:
python eval.py --output results.json

# Run a specific test:
python eval.py --test "demo before"
```

The eval suite runs 3 test cases (identical images, demo before→after, reversed) and scores the pipeline across 11 dimensions including semantic quality, confidence validity, RAG utilisation, and documentation length.

---

## Limitations

- Requires screenshots for comparison — does not do live DOM inspection
- Gemini free tier: 15 RPM, 1,500 RPD
- Vision analysis adds ~1–2s latency per detection
- RAG requires 2 embedding calls per generation (cached in future roadmap)

---

## Future Work

- [ ] Embedding cache to reduce RAG latency
- [ ] Support for video / GIF comparisons
- [ ] Multi-language documentation generation
- [ ] Webhook integration (trigger on CI/CD screenshot upload)
- [ ] Slack / Discord notifications on PR creation
- [ ] Fine-tuned confidence calibration using labelled evaluation data

---

## License

MIT License — free to use for portfolio or commercial applications.

---

## Author

**Anshita Bhardwaj** · [GitHub @Anshitaa](https://github.com/Anshitaa)

---

*Built to solve the real problem of documentation drift in fast-moving teams.*
