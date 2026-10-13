# Security and privacy

Report vulnerabilities via a private GitHub security advisory when available,
or contact the owner privately. Do not post credentials, transcripts, state or
personal information in public issues.

Production uses keyless IAM identities. Local opt-in gcloud credentials capture
short-lived tokens in memory; `GCLOUD_ACCOUNT` optionally selects the identity.
Never commit `.env`, private keys, credential JSON, Terraform state/plans, runtime
metadata or raw reports. Firebase browser config is public, not an Admin credential.

Gateway verifies Firebase anonymous tokens and owns histories/quotas. Firestore
transactions protect ownership and limits. Runtime is private; direct browser
Firestore access is denied. Reference rules do not override another project's
permissive rules: inspect the full ruleset. CORS is not an authentication boundary.
Local auth bypass is forbidden in cloud; keep development servers on localhost.

Catalog data is untrusted evidence. Agent controls require grounded IDs and API
cards use canonical prices/links, but natural-language accuracy is not guaranteed.

Bounded chat history and anonymous UIDs persist in Firestore with 30-day inactivity
expiry and TTL deletion. Expired histories are rejected before asynchronous deletion.
Metadata-only telemetry omits prompts, responses, tool payloads, identities and
credentials; native ADK spans pass through an allowlist sanitizer. Visitor throttling
is five admitted turns/minute, alongside global quotas. It does not prevent new
anonymous identities or provide edge DDoS protection. Public traffic can incur costs
despite chat limits; alerts are not hard spending caps. See the detailed
[threat model](docs/THREAT_MODEL.md) and [privacy controls](docs/HARDENING.md).
