# Contributing

Read [architecture](docs/ARCHITECTURE.md) and [setup](docs/LOCAL_SETUP.md). Use a
feature branch and PR describing the behavior change and relevant validation.
Preserve demo/historical labeling, canonical cards and server ownership/quotas.

Run backend pytest for Python changes and build/relevant browser tests for UI
changes. Stage shared code with `scripts.stage_agent` before isolated agent tests;
edit `beauty/`, not its generated copy. Live tests incur charges and need deliberate
authorization. No automatic production deployment should be added by default.

Do not submit downloaded products/images, transcripts, credentials, state or raw
reports. Blank templates and clearly synthetic test fixtures are fine; fixtures
must not become the live catalog. Preserve notices and document dependencies.
Explain model/resource-limit changes with their quality/cost impact.

Before publishing, stage the intended files and run
`python -m scripts.check_public_repo`. It checks staged paths and common credential
patterns without printing potential secrets. This heuristic check complements
manual review; it cannot prove that every possible secret is absent.
