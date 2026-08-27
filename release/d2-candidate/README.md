# D2 public clean-install candidate

This directory contains the immutable D2 clean-install acceptance bundle generated from UNIFY revision `7fd5923ec04e912fd28d17b16018aa76d5a4378a`.

## Files

- `alicactl` — Linux amd64 native installer candidate
- `manifest.json` — signed `alica-release/v1` development manifest
- `manifest.signature.json` — detached manifest signature
- `public-key.json` — pinned D2 acceptance public key
- `install-request.json` — isolated clean-host request
- `SHA256SUMS` — transport checksums

The manifest pins all runtime images by digest. The clean-host workflow starts with no GHCR credentials and fails closed unless those exact images can be pulled publicly and the full eight-service Cell becomes healthy.

This remains a development acceptance bundle, not a production signing or general-availability release.
