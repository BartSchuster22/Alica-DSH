# ALICA Community DSH 1.0 — Independent Operator Guide

## Obtain and verify

Use only the public `BartSchuster22/Alica-DSH` release and exact published checksums. Online operation uses immutable OCI digest references and signed metadata. Offline operation uses the complete `.bundle.tar.zst` and verifies `SHA256SUMS` before import. Never disable signature, expiry or digest verification.

## Supported host

Clean Debian 13 amd64 with systemd, Docker Engine `>=28.4.0 <29.0.0`, Compose `>=2.39.4 <3.0.0`, at least 4 vCPU, 8 GiB RAM and 100 GiB free SSD. Recommended: 8 vCPU, 16 GiB and 200 GiB SSD.

## Acceptance sequence

1. Read the EULA, support, security and privacy documents.
2. Verify the offline checksum/signature inventory or online signed metadata.
3. Supply a closed install request, explicit EULA digest acceptance, local administrator and BYOK secret-file reference.
4. Run `alicactl plan`, then `alicactl install`; repeat install and require a non-mutating no-op.
5. Run `status`, `verify`, authenticated QA10, synthetic alert, backup and restart checks.
6. Keep the backup encryption key separately from S3-compatible storage credentials.
7. Apply only signed, exact-origin updates after reviewing risk and compatibility declarations.

No source checkout, Node, pnpm, private registry credential, ALICA staff action or central service is an operator prerequisite.
