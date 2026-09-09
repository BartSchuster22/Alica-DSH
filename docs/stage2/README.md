# Stage 2 — bounded engineering release

Release: `dsh-stage2-72a4812` (Linux amd64).

This is the rebuild Stage 2 line, not the historical D6 line. D6 signatures, SBOMs, offline-host acceptance and support claims do **not** apply to this bundle. Stage 2 is not production/GA approval.

## Download and prepare

Use the pinned [release](https://github.com/BartSchuster22/Alica-DSH/releases/tag/dsh-stage2-72a4812). The release is publicly verified only when its `public-download-verification.json` receipt is attached.

The self-contained bundle contains all seven runtime images and the installer. The target does not clone source or build applications. Install Docker Engine + Compose v2, Python 3.11+ and OpenSSL 3 first. The qualified target was Linux amd64 / Ubuntu 26.04; no other OS/architecture or pristine-OS/offline matrix is claimed. Plan for at least 8 GiB RAM and 30 GiB free space for a cold download, extraction and Docker image import. The installer also enforces its live resource and ownership checks.

Run `bash scripts/prepare-stage2.sh /path/to/new-private-directory`, or download the archive directly and verify:

```
e4935f81096561ec41050250e20f6d0a62dd7e3cd3d9bf4b37607860752964fb  dsh-stage2-72a4812-linux-amd64.tar.gz
```

Archive size: 1,580,213,468 bytes.

Copy `request.example.json` to `request.json` and configure a unique cell name, owned DNS hostname, matching HTTPS port/bind, and first-owner username. Example:

```json
{"cell":"dsh2-mybox","origin":"https://dsh.example.com","port":443,"bind":"0.0.0.0","owner":"owner"}
```

Use an unused listener. Resolve that DNS name to the target. Protect the extraction directory from other users. From the extracted bundle:

```sh
sudo python3 install.py plan --bundle "$PWD" --root /srv/dsh2-mybox --request request.json --release-sha256 bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2
sudo python3 install.py install --bundle "$PWD" --root /srv/dsh2-mybox --request request.json --release-sha256 bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2
```

The root basename must match the requested cell. Existing unowned roots, conflicting release/request identities and unsafe paths are rejected. Do not use the qualification example unchanged on the development host.

## First owner, trust and native model setup

- The installer generates an engineering CA and HTTPS certificates. Securely export the **public** `/srv/dsh2-mybox/secrets/framework-ca.crt` and enroll it in the client trust store after checking it against the target. Never export its private key. Do not bypass TLS verification. Certificate renewal/production PKI is not closed by Stage 2; generated certificates have a bounded lifetime.
- Read the temporary first-owner password locally as root from `secrets/owner-password`. Continue through the UI's secure sign-in link. Keycloak requires a password change and may require completion of the owner profile.
- Keycloak owns identity passwords. Core password login is disabled. Core uses one-use PKCE state, signed-token validation, encrypted session token storage and live identity-session checks. Public Keycloak administrative/master routes are blocked.
- Core's runtime database role is not the migration/bootstrap administrator and cannot read Keycloak's identity tables.
- Configure providers/models through the Hermes-owned UI. No provider credentials are shipped. A new installation requires the operator's own provider authorization. Device OAuth consent is a human step.
- Qualification exercised `openai-codex` / `gpt-6-astra` with an authorized, access-only native fixture. No existing operator refresh credential was copied. This proves bounded inference and retention, not unattended OAuth renewal or a new user's completed consent flow.

## Recovery and rollback

Root-operator owner recovery uses Keycloak, not a shadow Core password:

```sh
sudo python3 recover_owner.py --bundle "$PWD" --root /srv/dsh2-mybox --request request.json --release-sha256 bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2
```

It resets the owner's temporary password, requests identity-session logout and reports the root-only recovery-password file. A subsequent login must change that password.

Installation failures stop only the owned candidate and retain its data. Retry the exact same `install` command with the same verified bundle/request. An already installed cell is rechecked/restarted rather than being blindly reported healthy.

```sh
sudo python3 install.py stop --bundle "$PWD" --root /srv/dsh2-mybox --request request.json --release-sha256 bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2
sudo python3 install.py start --bundle "$PWD" --root /srv/dsh2-mybox --request request.json --release-sha256 bcf5d5e2d063518923e2dc92068c7f467c57357e88ada1cc09b4b25a75581aa2
```

Stop is the tested rollback action; it retains containers, volumes and the private installation root. Do not delete those or use global Docker prune. Cross-release migration, disaster restore, production promotion and long-term lifecycle guarantees belong to later stages.

## Exact evidence and scope

See [EVIDENCE.json](EVIDENCE.json). Acceptance used a fresh owned namespace on the authorized development host, with existing image cache and unrelated workloads retained. It included a deliberately failed transaction after a committed database write, successful same-bundle retry, strict HTTPS login, credential/security negatives, native inference, restart retention, browser rendering and owner recovery. The guard stopped the final candidate and observed existing workloads unchanged. This is not a pristine-OS or disconnected-host acceptance claim.

Installer source: `72a4812b4be8c164bbb24ee9b4e73466bcc40451` in UNIFY. Core/UI runtime source: `e44d8fc86849471869f10a1cb0f849cfb7c23c7b`. Keycloak build source: `1f66de17238cd310f56fc3a501750a417ecaecdc`. Exact image IDs and file hashes are inside `release.json`; private source access is not required to install the artifact.

## Explicit uninstall and credential rotation

The bundled `alicactl` is the Stage 2 single-writer entry point. Its `uninstall` action removes only owned containers and networks, retains named volumes and installation secrets, and journals `uninstalled-data-retained`. `install` with the same pinned manifest and request recreates the services against those retained stores. Never use volume deletion or global Docker pruning as uninstall.

Application credential rotation is deliberately staged: issue a replacement scoped grant; verify and deploy the replacement; revoke the original grant. The original must return 401 after revocation while the replacement continues to read its own project. Cross-project access remains denied. There is no claim of an atomic consumer rollout.

Ingress request bodies are explicitly capped at 1 MB. The 72a4812 candidate adds the explicit uninstall contract; f390298 remains historical preview evidence. Final Stage 2 closure requires the separate public-install acceptance record.
