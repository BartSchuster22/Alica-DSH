# Security Policy

## Reporting

Report suspected vulnerabilities privately to **security@alica.hk**. Include affected release ID, manifest digest, reproduction steps, impact and any suggested mitigation. Do not include customer data, credentials or signing keys.

ALICA Ltd provides no response-time or remediation SLA for the free Community edition. We will make a reasonable effort to acknowledge actionable reports, investigate them and, where warranted, publish signed withdrawal/revocation metadata, mitigation guidance or a replacement candidate.

## Release security boundary

A supported candidate must use immutable OCI digests, a signed whole-Cell manifest, threshold update metadata, checksum-bound offline content, explicit EULA acceptance, local secret files, no central runtime dependency, encrypted off-host recovery and fail-closed lifecycle validation.

Publication is blocked by unresolved P0/P1 acceptance findings, invalid or missing signatures, secret leakage, unknown required artifacts, incompatible licensing, unauthenticated private dependencies, or failed independent online/offline acceptance.

## Operator responsibility

Operators are responsible for host patching, firewalling, physical access, credentials, provider and backup services, certificate/DNS configuration, reviewing signed release notes, applying approved updates and testing recovery material.
