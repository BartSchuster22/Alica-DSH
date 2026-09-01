# ALICA Community DSH 1.0 — Data and Privacy

The Community DSH is local-only and has no PSI, UPRM, Fleet, Modelm8 or other ALICA central runtime dependency. Customer content and operational telemetry are not sent to ALICA Ltd by default.

## Data authorities

Durable data includes PostgreSQL UNIFY/Identity data; Alica and Herman native state; MemoryV4 data and backups; AInbA state; Doghouse observations/incidents; Caddy and release configuration; lifecycle state, operation journal and evidence; and local secret/recovery references.

Configured BYOK providers, DNS, time, certificates, update metadata and S3-compatible backup destinations receive only traffic required for the operator-selected integration. They are independent third parties governed by their own terms.

## Export, backup and deletion

`alicactl backup` creates a checksummed, encrypted Cell recovery artifact and replicates it to the configured off-host destination. Operators retain encryption keys separately. Uninstall/purge is not authorized by the D6 candidate; deletion is manual and must include Cell volumes, installation state, local/off-host backups and separately held secrets according to operator retention obligations.

No support bundle is uploaded automatically. Evidence is local, explicit and redacted; secret values must never appear in manifests or acceptance evidence.
