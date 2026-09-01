# ALICA Community DSH D4 candidate

Signed recovery and operations candidate.

- Release: `rel_01a05d82-be23-7079-a700-13651201b7d2` / `1.0.0-d4.candidate.1`
- Manifest digest: `sha256:6f9891aeb869f1e31ac84ad67463f374a649efd0cce28b31c5f273a4d19904c6`
- UNIFY source: `38980813a55204ea4a3ad77ca3fd9e11d20c94c9`
- UNIFY tree: `sha256:2f62cf6de53ab7b69b3083d8562056cee996025354e98575102fc27384043160`
- alicactl digest: `sha256:6ba4083c3ed00ba315fa3ea43edea07fcf3e8d7188d27063883a769c8f4abbc2`
- Scope: coordinated AES-256-GCM backup, S3-compatible off-host replication, authenticated isolated same-release restore, restart/reboot recovery, persistent systemd backup/canary timers, drift/health/backup-age/disk/certificate checks and webhook alerts.
- Recovery and S3 credentials must be separately provisioned root-owned mode `0600` files; placeholders in the example request are never credentials.
- Not authorized: D5-D6 updates, cross-release compatibility/rollback, production trust/channel custody or GA.
