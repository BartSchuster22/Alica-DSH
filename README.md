# Alica-DSH

Canonical public distribution repository for **ALICA Community DSH**.

## Rebuild Stage 2 engineering line

See [the Stage 2 operator guide](docs/stage2/README.md) and [pinned release](https://github.com/BartSchuster22/Alica-DSH/releases/tag/dsh-stage2-72a4812). Publication is verified only when the release download receipt is attached. Stage 2 is not production/GA approval.

## Historical D6 independent candidate

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

## Rebuild Stage 3 engineering line

[External reference integration — bounded engineering PASS](docs/stage3/README.md).
[Application contract/schema](docs/stage3/CONTRACT-V1.md) and
[standalone customer reference app](reference-app/README.md).
Stage 3 acceptance is not production/GA approval; Stages 4–7 remain separate.
