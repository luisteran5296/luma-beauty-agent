# Gateway API

Live base URL: [LIVE.md](LIVE.md). Local: `http://127.0.0.1:8000`.
Interactive OpenAPI documentation is at `/docs`.

| Method/path | Auth | Behavior |
|---|---|---|
| `GET /health` | Public | Status, catalog count/version, agent configuration |
| `GET /api/products` | Public | Filtered records, complete catalog count, categories/version |
| `GET /api/products/{product_id}` | Public | Canonical record or 404 |
| `POST /api/chat` | Firebase ID token | Reserve turn and stream response |

Product query: `q` (up to 200 characters), `category`, `max_price` (USD, 0–100,000).
`total` is the whole catalog count, not matched rows. Ratings/counts may be null.
USD display price is numeric; original Decimal fields serialize as strings.

## Chat

Header: `Authorization: Bearer <Firebase ID token>`, obtained after anonymous
Firebase sign-in. Never put service-account keys in a browser.

```json
{
  "session_id": "2fd2589f-30b2-4290-aef5-4e7dd63264b0",
  "request_id": "ed9cf7f7-c5a0-40d6-bc60-808ab3b2b441",
  "message": "Find a moisturizer under $20."
}
```

Use one session ID per conversation, a fresh request ID per attempt. Message
length is 1–1,200 characters, not whitespace-only. Server owns history and quotas.

Response: `text/event-stream`. Frames have `event:` and JSON `data:` lines followed
by a blank line. Wait for `done` before sending a follow-up.

| Event | JSON fields | Meaning |
|---|---|---|
| `status` | `message` | Progress |
| `answer` | `text` | Validated final answer |
| `recommendations` | `products` | Canonical cards |
| `done` | `turns_remaining`, `usage` | Successful turn committed |
| `error` | `message`, `turns_remaining` | Failed stream; attempt consumed quota |

Cancellation releases the lease but can consume allowance. Truncated/empty runtime
streams fail. This is event streaming, not per-token output.

## Errors

| Status | Reason |
|---|---|
| 401 | Missing/invalid/expired Firebase token |
| 404 | Unknown product |
| 409 | Different owner, repeated request or outstanding lease |
| 422 | Invalid UUID, message or filters |
| 429 | Session/monthly conversation/message limit |
| 503 | Catalog/agent unavailable or quota check failed |

After streaming begins, failures arrive as SSE `error` events, not a new HTTP
status. Logs retain usage/latency and error classes, not raw visitor prompts/headers.
