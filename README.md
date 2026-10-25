# studio-credit-guard

A credit guard for paid generation APIs: runs start as requests with model and credit cost, a typed approval naming the count arms a single run, the guard relocks after, and a ledger records cost per run.

![Demo](docs/demo.gif)

## Quick start

```
python demo.py
```

Runs the whole gate end to end against the real hooks and CLI, in a temp state dir. Tests: `python -m unittest discover -s tests`.

## Requirements

Python 3.8+. No dependencies.

## How it works

- The agent files a request: `python -m creditguard request "intro clip" --model video-x --settings "720p 5s" --cost 12`.
- Only a human can approve. The `approve` hook (UserPromptSubmit) reads the prompt; typing `go 12` approves the pending request that costs exactly 12 credits. A wrong count approves nothing, and a negated phrase ("do not go 12") is ignored.
- `python -m creditguard arm <id> --quoted <cost>` arms exactly one run, and refuses if the quoted price differs from what was approved.
- The `guard` hook (PreToolUse) denies any generate command unless an arm is live, and spends the arm on first use, so a retry is locked again. Arms expire after 5 minutes.
- Every run lands in a CSV ledger; `python -m creditguard ledger` prints the total. Optional `CREDIT_BUDGET` caps cumulative spend.

Hook wiring for Claude Code (`settings.json`):

```json
{"hooks": {
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python creditguard/hooks.py approve"}]}],
  "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python creditguard/hooks.py guard"}]}]
}}
```

Set `CREDIT_GENERATE_PATTERN` to a regex matching your tool's paid command.

## Results

Measured from the author's own use of the guard around a paid video and image service, totals only, no prompts or project names. Requests were filed 20 to 23 Oct 2026.

| Measure | Count |
| :--- | ---: |
| Requests filed | 32 |
| Approved by a typed approval | 20 |
| Never approved | 12 |
| Approved requests that ran | 13 |
| Approved requests that never ran | 7 |

- 12 of 32 requests were never approved, and none of them spent a credit. All 354 credits spent came from the 13 approved requests that ran, out of 514 credits approved.
- 29 requests were drafts, 2 were stills and 1 was a final render.
- The hook that protects the approval state denied 7 attempts to edit it, 23 to 25 Oct 2026.

## License

MIT. See [LICENSE](LICENSE).

Built with Claude Code. More: https://made-by-asking.pages.dev/showcase/studio-credit-guard/
