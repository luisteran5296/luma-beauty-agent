# Validation record · October 13, 2026

Recorded checks are not a guarantee of future model behavior. Raw reports remain
local/ignored because they can contain answers, catalog data or cloud diagnostics.

| Check | Result |
|---|---|
| Backend pytest | 52 passed; CI skips two snapshot tests when private catalog is absent |
| Agent serving tests | 3 passed; 6 opt-in live scaffold tests skipped |
| Hardening security suite | 20 scenarios, 22 checks/turns passed |
| Native offline grading | All 14 grades complete: quality mean 4.86/5, minimum 4; safety 14/14 |
| Frontend | Production build and 9 browser tests passed |
| Terraform | Init/validate passed; reviewed plans subsequently applied |
| Catalog | 100 unique complete records, primary images HEAD 200 at selection |
| Embeddings | 100 matching 768-dimensional vectors |
| Live catalog evaluation | Seven turns passed budget/comparison/vague/cleanser/no-match/missing-ingredient/invented-product scenarios |
| Hosted API | 100 products; Firebase anonymous auth works; missing token 401 |
| Isolation | Another visitor's session reuse returns 409 |
| Private resources | Browser Firestore denied; unauthenticated runtime 401 |
| Hosted browser | 100 cards, demo banner, mobile/desktop modal, three real recommendation cards |

Backend checks cover schema/currency/ratings, checkpoint imports, filters, atomic
refresh, embedding mismatch, concurrent quotas, replay/lease/ownership, month
rollover, auth, canonical cards, forced retrieval, budgets and truncated streams.
Browser checks cover cart, details, filters, streamed events/errors, modal focus,
launcher transitions, reduced motion and mobile fit. Final avatar: peach sun shape.

Seven real-catalog turns used 12,209 input / 681 output tokens and 191.2 seconds
locally including credential overhead. Hosted browser chat took 9.33 seconds.
These small samples do not establish long-chat performance or independent accuracy.
Earlier three empty-catalog agents-cli rubric cases scored 5/5; that baseline is
not a recommendation-quality guarantee. See [costs](COSTS.md).

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
Push-Location frontend
npm run build
npm test
Pop-Location
.\.venv\Scripts\python.exe -m scripts.stage_agent
```

Inside `agent/`, run `agents-cli install`, then
`uv run pytest tests/unit tests/integration`. Live integration is opt-in.
Model evaluations/hosted checks require credentials, incur charges and consume
allowance. Run intentionally; they are not routine offline CI.

## Limits

Historical metadata is not current inventory. Source rights are separate from
software licensing. Images can stop loading. No payments, orders, live inventory,
automatic retail-price refresh or managed Sessions migration is implemented.
Firestore inactivity TTL and Registry discovery are implemented. Broader release
needs independent evaluation and a privacy review for its intended audience.
