# Meeting Prep Briefing — Multi-Agent Network

A [neuro-san](https://github.com/cognizant-ai-lab/neuro-san) agent network that prepares a complete pre-meeting briefing from a single natural-language request — combining live web research, internal CRM context, and automated risk flagging into one composed answer.

Give it a company and a contact name. It researches both in parallel, pulls internal account context safely, flags anything risky or sensitive, and hands back a ready-to-use briefing — including catching cases where the company and person don't actually match.

> **📌 Where to look:** This repo includes the full `neuro-san-studio` framework this project is built on. **The project's own contribution is limited to a handful of files** — everything else is scaffolding needed to run it. Jump straight to [Files to review](#files-to-review) below.

---

## Example

**Input:**
> "I have a meeting with Sridhar Vembu from Zoho tomorrow. Prep me a briefing."

**Output:** a composed briefing with a company news snapshot, the contact's public background, internal account context (deal value band, relationship health), risks/sensitivities to be aware of, and a suggested conversation opener — each factual claim traceable to a real source URL.

---

## Files to review

Everything specific to this project lives here — **5 files total**:

```
registries/meeting_prep_briefing/
└── meeting_prep_briefing.hocon      ⭐ the network itself: all 5 agents,
                                         their instructions, and how they're wired together

registries/manifest.hocon               1 line added (see below) to register
                                         the network so the server serves it

coded_tools/meeting_prep_briefing/
├── __init__.py                         package marker (no logic)
├── account_context_tool.py          ⭐ sly_data-backed CRM lookup
└── citation_filter.py               ⭐ URL-verified citation enforcement
```

The only change in `registries/manifest.hocon` is this one line, added just before the file's closing `}`:
```hocon
"meeting_prep_briefing/meeting_prep_briefing.hocon": true,
```

The three ⭐ files are where all the actual design decisions live — the agent instructions, the sly_data boundary, and the citation-verification logic. Everything else in this repo (`neuro_san_studio/`, `apps/`, `docs/`, `tests/`, `servers/`, `middleware/`, etc.) is the underlying framework, unmodified, kept in place only so the project can be cloned and run without a separate install step.

---

## Architecture

8 nodes: 5 reasoning agents (LLM-driven, coordinated via the AAOSA protocol) + 3 supporting tools (no LLM reasoning, direct execution).

```
                        ┌─────────────────────────┐
                        │  meeting_prep_briefing   │   ← front-man
                        │      (front-man)         │      (only agent the user talks to)
                        └────────────┬─────────────┘
                                     │  delegates in parallel
          ┌──────────────┬──────────┼──────────────┬──────────────┐
          ▼              ▼          ▼              ▼              ▼
 company_news_      person_    account_context_             risk_flagger
 researcher         researcher specialist
     │                  │            │                            ▲
     ▼                  ▼            ▼                            │
 ddgs_search      ddgs_search  AccountContextTool                 │
     │                  │            │                            │
     ▼                  ▼            │                            │
 citation_filter  citation_filter    │                            │
     │                  │            │                            │
     └──────────────────┴────────────┴────────────────────────────┘
                    validated findings feed into risk_flagger,
                    then everything returns to the front-man
                    for final composition
```

### Reasoning agents (5) — all defined in `meeting_prep_briefing.hocon`

| Agent | Role |
|---|---|
| `meeting_prep_briefing` | Front-man. Parses the request, asks for missing info (company or person name), delegates to the four agents below, and composes the final briefing. |
| `company_news_researcher` | Researches recent public news about the company (earnings, leadership changes, layoffs, controversies). |
| `person_researcher` | Researches the contact's public professional background. |
| `account_context_specialist` | Retrieves internal account context (deal value band, relationship health) via `AccountContextTool`. |
| `risk_flagger` | Synthesizes all research + account context into risks, sensitivities, and rapport-building points. |

### Supporting tools (3)

| Tool | Type | Defined in | Role |
|---|---|---|---|
| `ddgs_search` | Toolbox tool | framework (pre-built) | Live web search (no API key required), shared by both researchers. |
| `citation_filter` | Coded tool (Python) | `coded_tools/meeting_prep_briefing/citation_filter.py` | Mechanically verifies every claimed source URL against the URLs actually returned by search — discards any claim it can't verify, before it ever reaches the final briefing. |
| `AccountContextTool` | Coded tool (Python) | `coded_tools/meeting_prep_briefing/account_context_tool.py` | Looks up a company's internal account record and returns only a safe, bucketed summary — the raw record never enters the LLM's context. |

---

## Key design decisions

**Parallel research, not sequential.** The front-man is instructed to call `company_news_researcher` and `person_researcher` without waiting on one before the other — cutting total response time roughly in half compared to a sequential chain.

**Citations are enforced in code, not just prompted.** Researcher agents are instructed to attach a source URL to every claim, but an instruction alone doesn't guarantee accuracy. `citation_filter` checks each claim's URL against the real search results and drops anything that doesn't match — so a hallucinated citation can't reach the user.

**Internal data never touches the LLM prompt.** `AccountContextTool` writes the full internal account record to `sly_data` — a side-channel that coded tools can read/write but that is structurally excluded from the LLM's context. Only a bucketed, non-sensitive summary (e.g. `"Strategic-tier (> $150K)"` instead of the exact deal value) is ever returned to the model, and only one field of that is allow-listed to reach the end user.

**The network catches its own mismatches.** If the company and contact don't actually match public records (e.g. a person is named alongside the wrong company), `risk_flagger` surfaces this as the top risk rather than silently blending both threads together — and the front-man will proactively ask the user to confirm before researching further.

---

## Tech stack

- [neuro-san](https://github.com/cognizant-ai-lab/neuro-san) — multi-agent orchestration framework, AAOSA delegation protocol
- Claude Sonnet — reasoning model for all agents
- DuckDuckGo Search (`ddgs`) — live web search, no API key needed

---

## Running it

### 1. Clone and set up a virtual environment

```bash
git clone https://github.com/ovkrishna/meeting_prep_briefing_agent.git
cd meeting_prep_briefing_agent
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
uv add neuro-san-studio
```

### 3. Set your LLM API key

This project uses Claude Sonnet, so set your Anthropic key (or add it to a `.env` file in the project root):

```bash
export ANTHROPIC_API_KEY="XXX"
```

Optionally verify it's picked up correctly:

```bash
ns check-llm-keys
ns check-config
```

### 4. Start the server and UI

```bash
ns run
```

This starts the neuro-san server (`localhost:8080`) and the nsflow chat UI (`http://localhost:4173/`). In the UI, select **meeting_prep_briefing** from the list of agent networks, then try:
> "I have a meeting with [contact name] from [company name] tomorrow. Prep me a briefing."

---
## Working view
<img width="1885" height="932" alt="Working view" src="https://github.com/user-attachments/assets/32a0b6ec-6cfc-4c61-bad7-9d368b51d31e" />


## Limitations

- `citation_filter` verifies that a cited URL was genuinely returned by search — it does not verify that the page content actually supports the claim (that would require fetching and reading each page).
- `AccountContextTool` uses a mock internal account dataset for demo purposes; swapping in a real CRM API would be a drop-in replacement of the coded tool's data source.
