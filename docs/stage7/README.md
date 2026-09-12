# Stage 7 QA candidate — NOT accepted / NOT production-ready

This is an immutable assembled candidate for independent Stage 7.1–7.3 testing. Publication, checksum verification and QA signature verification do **not** prove installation, security, restore, update or workload acceptance. Earlier Stage 2/D6 releases and Stage 5/6 restored-state PASS results do not qualify this candidate.

## Pinned identity

- Artifact: `dsh-stage7-qa1-ed2f09b-linux-amd64.tar.gz`
- Archive SHA-256: `171bfef29467825548cba0c669f14bbe0620178ae546ff8c5dab288b3b334a88`
- Release SHA-256: `f3ce059a6e2c1b575ead2fb6e6dbededa4420505285ac9220d5a9ea2b13a9da3`
- Assembler source: UNIFY `ed2f09b62bc93c03597dcc8a2ed6104cb1c989b9`.
- Host operations source: Doghouse `585494dd0368bdc9ae0cc95586a0ead7e074bab6`.
- QA key ID: `9b02c8bc02a6b8081031519e192bd508f74d305d1dab9fe28af4440e8b833ac6`.
- External trust-file SHA-256: `5af48e80bffa12df7921c2c688f4f2f2249c68032d04e6f7e10621668d264034`.

The trust anchor is QA-only. Obtain/verify it against the pinned identity above independently of the candidate bundle. Never accept a key supplied by arbitrary candidate code. The detached envelope is time-limited; an expired envelope is denied, not bypassed by changing the clock.

The bundle contains seven pinned platform images plus the independent reference-application image archive. There are no customer databases, provider credentials, owner passwords or private signing keys in the bundle. Images are observed predecessor images, not a reproducible-build claim. Credentials and installation identities are created/configured on the target.

## Bounded operator preparation

Use an empty, disposable Linux amd64 environment. The intended qualification environment is Ubuntu 26.04, Docker 29.1.3, Compose 2.40.3 and overlay2. These are qualification prerequisites, not a claim that the independent run has passed. Measured smaller-host minimums and peak usage are still pending.

Required tools: Python 3 with `cryptography`, Docker/Compose, OpenSSL and curl. No source checkout or image build is required on the target. The Stage 2 installer retains its existing admission limits; do not bypass insufficient-memory/disk or health failures.

1. Download the archive, detached envelope and pinned public trust over HTTPS from this immutable prerelease.
2. Check the archive and trust SHA-256 against the values above. Keep the trusted verifier and trust file outside the extracted bundle, under root-owned, non-writable ancestry.
3. Extract only the archive's regular files under `bundle/` into a new empty root-owned directory. Refuse links, duplicates, traversal, special files and any unexpected path. Do not execute bundle code before admission.
4. Run the separately published `release_trust.py verify` with `--scope qa`, `--installed-sequence 0`, and `--current` equal to 64 zero characters. The zero predecessor means a **virgin installation**, not an upgrade allowance. Supply the extracted bundle, envelope and externally pinned trust file.
5. Use the admitted bundle's `alicactl` with an explicit request. For this QA run: cell `dsh2-stage7-qa1`, root `/opt/dsh2-stage7-qa1`, an operator-controlled HTTPS hostname, port 443 and loopback bind. The root basename must equal the cell. No restored owner/credential/database state may be imported into clean-install acceptance.
6. Complete genuine OIDC/owner setup, native provider configuration and application registration with newly generated credentials. The reference image is provided separately; application credentials belong to its backend, never browser code. Full end-to-end setup and independent acceptance evidence remain pending.

`alicactl` is the single-writer lifecycle entrypoint. Failed installs retain their diagnostics/data and must not be labelled PASS. Stop/uninstall retain owned data; deleting stores or rebuilding a host requires verified recovery copies and explicit ownership checks.

## Exclusions

No production routing, PSI activation, licence change, GA release or Stage 7.4–7.6 approval. No day/week soak, unmeasured provider-cost guarantee or general database migration claim. Refer to the later independent acceptance record, when one actually exists; this candidate intentionally carries `stage7Accepted: false`.

## Correction provenance
This new immutable candidate corrects CLI lifecycle routing through host operations and explicit bind-file modes under restrictive umask. The original 4273c86 public candidate failed a fresh DSH2 installation at PostgreSQL secret readability. No acceptance is inherited. Six packaging/regression tests passed on the development host; target acceptance is pending.
