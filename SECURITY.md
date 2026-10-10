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

Bounded chat history and anonymous UIDs persist in Firestore; no age-based deletion
is implemented. Define retention before wider use. Gateway metrics omit prompts/
headers; automatic ADK telemetry is disabled. Public traffic can incur costs despite
chat limits; alerts are not hard spending caps.
