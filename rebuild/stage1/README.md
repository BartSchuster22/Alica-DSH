# Stage 1 — qualified engineering baseline

**Runtime gate: PASS, 2026-09-09.** This is a bounded engineering baseline, not a production release or public installer. Stage 2 remains unauthorized/unstarted by this receipt.

## Qualified scope

- Exactly seven services: one Hermes runtime, UNIFY Core, UniUI, MemoryV4, PostgreSQL, Keycloak and Caddy.
- Ubuntu 26.04 / Docker 29, admitted against observed headroom and explicit candidate limits. No inherited Debian/downgrade/physical-8-GiB requirement was used as a DSH-2 gate.
- Four internal backend networks. Only Caddy joins the candidate ingress bridge; only `127.0.0.1:18443` is published. A private test CA is verified by the host-side TLS probe. No production route change.
- Real authenticated Hermes contract, native profile/cron/Kanban CLI, private Core-to-Memory health, seven healthy services, stop/restart and native test-project persistence passed.
- Existing-workload preservation and existing UI HTTPS 200 passed. Candidate stopped after the exercise. No existing workload was removed or reused.
- MemoryV4 owns private SQLite storage; it is not a PostgreSQL consumer. PostgreSQL serves Core, Keycloak and the Hermes adapter event journal.

## Artifact and evidence ownership

`candidate/` contains the public-safe engineering receipt, image identities/layers, declarative Compose template, one-framework registration, source revisions, matching build metadata and checksums. The assembler rehashes the real image archive and verifies every selected config and ordered filesystem identity before producing this receipt.

Full live inventories, host identity, private paths, observations and failure records remain in **private PROJECT-ALICA evidence**. The public runtime receipt binds that raw evidence by SHA-256 without copying it. The hash-named image archive and executable exercise package remain in the private engineering artifact store; no image binaries or credentials are published here.

The executable admission/render/exercise/transport harness remains owned by **UNIFY**, at `dsh/rebuild/stage1/` and the commit in `candidate/source-revisions.json`. This repository owns distribution assembly, not framework internals. The already-qualified target retains stopped candidate-only test data; the fresh-install harness correctly refuses that occupied namespace. This is not an instruction to delete it or any other host data.

To assemble again with authorized access to the private inputs and a fresh output directory:

```sh
python3 rebuild/stage1/assemble_candidate.py "$PRIVATE_PACKAGE" "$PRIVATE_RUNTIME_EVIDENCE" "$FRESH_OUTPUT"
python3 -m unittest discover -s rebuild/stage1 -p 'test_*.py' -v
```

The assembler rejects a failed/incomplete runtime report, changed existing inventory, runtime/image mismatch or archive/config/layer mismatch. Its input `source-revisions.json` records exact recipe revisions. Build metadata can show a preceding HEAD plus working-tree changes; these are not represented as a signed clean-source public release.

## Limits and remaining stages

- No production readiness, workload-capacity, migration, backup/recovery or unattended-operation claim.
- Keycloak is healthy, but product OIDC identity binding is **not ready**.
- Public installer, signing and release delivery are **not ready**.
- Native source comparison covers the recorded 357 tracked Python files and declared overlays; it is not a complete third-party supply-chain audit.
- Hermes exited **137 with OOMKilled=false** under the bounded stop. The native test project survived restart, but graceful native-runtime shutdown remains **unqualified**, not silently counted as clean shutdown. See `candidate/final-stop.json`. This is not a disaster-recovery guarantee.
- The raw exercise admission description retains the earlier phrase “internal-only networks.” The actual qualified graph includes the Caddy-only ingress exception. The receipt and current harness correct that description without changing an admission predicate.

`qualify_host.py` and `sample_host.py` remain historical/read-only tools. The former checks inherited DSH 1.0 policy (`applies_to_dsh2: false`); it is not the revised candidate admission gate. Earlier blocked verdicts are retained in Git and private PROJECT-ALICA history, not current acceptance.
