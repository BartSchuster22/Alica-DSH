# Alica-DSH

Canonical public distribution repository for **ALICA Community DSH**.

## D6 independent candidate

The exact D6 candidate is under [`release/d6-candidate`](release/d6-candidate). It preserves every accepted D5 component byte while adding real bundled SBOM/provenance evidence, release documentation, signed trust metadata and a closed independent-acceptance matrix.

- [Operator guide](docs/OPERATOR.md)
- [D6 independent acceptance](docs/D6-INDEPENDENT-ACCEPTANCE.md)
- [Support lifecycle](SUPPORT.md)
- [Security policy](SECURITY.md)
- [Data and privacy](docs/DATA-PRIVACY.md)
- [Third-party notices](THIRD-PARTY-NOTICES.md)
- [EULA](licenses/ALICA-COMMUNITY-DSH-EULA-1.0.md)

The public D6 workflow builds a checksum-bound complete offline bundle, keyless-signs and verifies immutable OCI images, and runs the same authenticated acceptance matrix on separate online and disconnected clean hosts. Stable/general-availability promotion is not implied by candidate acceptance.

This repository must not contain private signing keys, registry tokens, generated installation credentials or unsupported release claims.
