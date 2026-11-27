# Web research-page audit

Goal: make `/research/<slug>` accurate. Use your existing report, result, strategy
and conversation history. **Do not run new backtests or launch grids.**

Write `web_audit.json` in your agent directory:

```json
{
  "slug": "your-agent-slug",
  "name": "Short display name",
  "tagline": "One sentence",
  "summary": "2-4 sentences: what the strategy actually does",
  "decision_process": "How a signal becomes a position; mention signal timing and fill timing",
  "rules": ["Rule 1", "Rule 2", "Rule 3"],
  "status": "Leader | Verified | Alternative | Fragile | Negative",
  "metrics": {
    "cagr10": 0.0,
    "dd10": 0.0,
    "cagr5": 0.0,
    "dd5": 0.0,
    "cagr10_5bp": null,
    "dd10_5bp": null,
    "cagr5_5bp": null,
    "dd5_5bp": null
  },
  "verdict": "Short honest verdict, including the main caveat",
  "sources": [
    {
      "idea": "The exact rule/claim this source supports",
      "source": "Author (year) / page title",
      "url": "https://...",
      "source_type": "paper | blog | book | report | data",
      "role": "inspired rule | supports assumption | benchmark | tested only | rejected",
      "evidence": "What exactly in the source supports it, or what you used it for",
      "confidence": "high | medium | low"
    }
  ],
  "rejected_sources": [
    {
      "source": "Author / page",
      "url": "https://...",
      "why_rejected": "What failed when tested or why it was not used"
    }
  ],
  "corrections": [
    "Any correction to the current web page, LEADER.md, or the report"
  ]
}
```

## Accuracy rules

- Every rule or claim should have a source entry, **or** be explicitly marked
  `"source": "Own test / no external source"`.
- Distinguish **inspired the rule** from **tested and rejected**.
- Do not invent URLs. If you only remember a paper title, use the URL from your
  report/history or leave the URL as `null`.
- Metrics must match your verified result, not the marketing headline.
- If 5 bp/10 bp was not measured, use `null`; do not guess.
- If the current web page has an inaccurate tagline, metric, or paper attribution,
  put it in `corrections`.
- Do not modify core files. Write only under your agent directory.

Reply with: `AUDIT WRITTEN`, the path, and the most important correction (if any).
