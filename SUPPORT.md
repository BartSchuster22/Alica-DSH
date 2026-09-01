# ALICA Community DSH 1.0 — Support and Lifecycle Policy

**Effective:** 2026-09-01
**Edition:** Community DSH 1.0

ALICA Community DSH is free self-hosted software supplied as-is under its EULA. No paid support, SLA, uptime, maintenance or update commitment is included. Operators own host security, credentials, certificates, providers, backups and recovery.

## Supported boundary

The qualified platform is Debian 13 amd64, systemd, Docker Engine `>=28.4.0 <29.0.0`, Compose `>=2.39.4 <3.0.0`, minimum 4 vCPU/8 GiB RAM/100 GiB free SSD and recommended 8 vCPU/16 GiB/200 GiB. Only `dsh-minimal/v1`, single-host and local-only management are covered.

Candidate releases are evaluation artifacts. Stable publication requires independent D6 evidence. Release metadata may withdraw or revoke unsafe candidates. No automatic update is enabled. Operators explicitly approve updates and retain separately custodied recovery material.

## Lifecycle

Security and compatibility notices, if issued, are published with signed release metadata. A release reaches end of distribution when its signed metadata is withdrawn or revoked. No minimum maintenance period is promised by the free license. Existing lawful use remains subject to the EULA, but revoked bytes may cease to be distributed.

## Assistance

Use the public repository issue tracker for reproducible documentation or packaging defects. Do not disclose vulnerabilities or secrets in public issues; follow `SECURITY.md`. Community responses are best-effort and not guaranteed.
