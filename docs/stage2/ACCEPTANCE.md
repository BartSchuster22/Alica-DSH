# DSH Stage 2 — as-built engineering acceptance

**Verdict: Stage 2 COMPLETE within the approved bounded engineering scope. Production-ready: FALSE.**

Author: Hermes Agent. Evidence: [machine-readable acceptance](EVIDENCE.json). This supersedes earlier Stage 2 pending/preview descriptions; it does not qualify Stages 3–7 or historical D6 claims.

## Immutable release

- Installer/component source: `72a4812610dbba7c0cd5a148b8eaa294b18559c9`, UNIFY branch `rebuild/stage2-secure-install`.
- Release: [dsh-stage2-72a4812](https://github.com/BartSchuster22/Alica-DSH/releases/tag/dsh-stage2-72a4812).
- Artifact: `dsh-stage2-72a4812-linux-amd64.tar.gz`, 1,580,236,798 bytes.
- Archive SHA-256: `e4935f81096561ec41050250e20f6d0a62dd7e3cd3d9bf4b37607860752964fb`.
- Release-manifest SHA-256: `bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2`.
- Complete immutable image identities, component provenance and file hashes are included in the acceptance JSON's release manifest.
- Earlier `f390298` remains immutable preview history, not final acceptance. The final attached acceptance record supersedes preview evidence in the distribution tag's initial documentation.

## Stage 2 acceptance map

| Plan task | Actual qualification |
|---|---|
| 2.1 Public transactional install | Anonymous HTTPS download and checksum verification; fresh namespace installation using only the downloaded bundle. No target source checkout or build. Current public artifact also passed an injected post-commit failure, rollback and reinstall with the committed value and original secret retained. |
| 2.2 Identity and recovery | Real Keycloak OIDC; wrong-password rejection; forced initial password change; owner and viewer sessions; cookie/CSRF and credential-class denials. Recovery invalidated the old password and required a new password before an authenticated Core session. Core ordinary password login disabled. |
| 2.3 Application credentials | Owner creates scoped grants. Two real native test projects prove positive own-project reads and cross-project denial. Replacement credential remains usable after original revocation. Viewer cannot list or mint credentials. Tokens are redacted from listing responses. |
| 2.4 Transport and boundaries | Strict CA/hostname verification; successful public-bundle login with a different hostname; explicit request-body limit and live 413 rejection. Core is non-superuser, cannot create roles/databases, and cannot read existing Keycloak identity tables. |
| 2.5 Native integration | Native inventory via authenticated Core and real native project creation/read. Native Hermes helpers configure credentials/model; no substitute native state store. |
| 2.6 First model | Real Hermes AIAgent inference using configured openai-codex/gpt-6-astra. Model selection and successful inference survived uninstall/reinstall. Operator refresh token was not copied. |
| 2.7 Local UI | Actual Playwright login and model/provider rendering after uninstall/reinstall; selected gpt-6-astra shown; zero JavaScript errors. Browser used an explicit leaf SPKI pin; strict CA validation was tested separately. |
| 2.8 Retry and retention | 24 installer tests passed. Live uninstall removed owned containers/networks, retained named volumes/secrets, and journalled the retained state. Reinstall restored healthy services and retained data. Same final public release passed injected-failure/retry acceptance. |

Relevant bounded contract scenarios: AC-05, AC-06, AC-08, AC-09, AC-10 and AC-12, for their Stage 2 portions. Full lifecycle, delivery, workload and production matrices remain later-stage gates.

## Scope and exclusions

Qualification used the approved Linux amd64 development host with fresh isolated installation stores. Existing OS, Docker and image cache were reused. This is not pristine-OS, cold-cache, offline, multi-platform or independent-cloud qualification. Existing workloads were preserved and all Stage 2 candidates are stopped; data/evidence remain retained. Temporary artifact listeners and firewall rules were removed.

Provider testing used an authorized access-only fixture imported through native Hermes credential/configuration helpers. Real inference was exercised; provider consent UI and refresh-token lifecycle are not claimed as automated tests. Credentials are not included in the public bundle. Credential rotation is staged replacement/deployment/revocation, not an atomic rollout across consumers.

The engineering private CA has a bounded lifetime and requires operator trust configuration. Certificate renewal, production hardening, signing/upgrade/restore matrices, durable external integrations and long-running workload qualification are not approved by this result.

## Operator and rollback guidance

Use the release's public preparation script and pinned checksum. Configure an explicit request with a unique cell/root, owned hostname and unused port. `alicactl` is the single-writer entry point; it accepts `plan`, `install`, `start`, `stop`, `uninstall` and the `recover-owner` dispatch. Lifecycle commands require the same bundle, manifest hash, root and request.

- `plan` performs preflight; it does not install.
- `stop` stops owned candidate services and retains data.
- `uninstall` removes owned containers/networks and retains named volumes and secrets, recording `uninstalled-data-retained`.
- `install` with the same pinned release/request restores services against retained stores.
- A failed transaction stops the candidate and retains data; retry with the same release/request.
- `recover-owner` is a privileged operator action. Its temporary password file remains private and the password must be changed on login.

Do not delete volumes, run global Docker pruning, import predecessor/customer data or replace an existing installation as part of this closure. Cross-release migration/restore is not qualified here.

**Stage 3 has not been started by this closure.**
