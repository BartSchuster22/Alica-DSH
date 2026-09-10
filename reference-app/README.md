# Independent Research Notebook reference app

A standalone Python 3.12+ / SQLite customer application. No private repository, framework SDK, npm package, Core login/session or direct Memory connection is required. It owns customer authentication, business conversation state, durable submission keys and callback effect deduplication. ALICA Core owns scoped service admission; Hermes owns inference; MemoryV4 owns governed knowledge.

**Status:** implementation with isolated SQLite and loopback HTTP tests (Core/inference explicitly mocked). A successful unit test does not establish live ALICA integration or Stage 3 acceptance.

## Provision through the operator, not the browser

1. In an installed ALICA instance, an authenticated owner registers the application using `POST /api/v1/applications`, with CSRF protection and native framework/project grants. Example manifest (replace project and subjects with operator-owned values):

```json
{"contractVersion":"alica-application/v1","name":"Research Notebook","frameworkId":"hermes-alica","projectId":"reference-research","subjects":["customer-alice","customer-bob"],"operations":["answer","research","refresh","correction"],"sourceUrls":["https://www.rfc-editor.org/rfc/rfc2606.txt"],"retentionDays":7,"promotionPolicy":"verified-extract-v1"}
```

For callbacks add `callbackUrl: "https://notebook.example.com/callback"` before registration. Port 443, reachable DNS, valid TLS and Core’s destination policy are required. Core supports exact operator-configured private callback address pins; never enable private research sources. Polling works without callbacks.

2. Store the returned `applicationId`, `credential.token` and optional `callbackSigningSecret` only on the backend. Credentials expire: issue a replacement through `POST /api/v1/applications/:id/credentials` (owner session/CSRF), atomically replace the private token file, restart this app, verify service and revoke the old credential. An expired/revoked token visibly pauses requests rather than inventing a result. Restart does not create new request identities. Callback signing secret rotation requires coordinated Core/app policy; no automatic undocumented rotation is claimed.

3. Generate customer password hashes interactively with `python3 app.py --hash-password`. No default passwords or public signup exist. Create a private JSON configuration:

```json
{"alice":{"subject":"customer-alice","passwordHash":"<generated scrypt hash>"},"bob":{"subject":"customer-bob","passwordHash":"<generated scrypt hash>"}}
```

Each subject has exactly one customer. The app persists the subject binding and rejects changes/removal on restart rather than reassigning old data. Password hashes may be rotated by the operator. Passwords are at least 12 characters; passwords/tokens are never exported. Failed logins are rate-limited; sessions expire after one hour. Production perimeter abuse protection and operator account lifecycle remain deployment responsibilities.

## Run privately behind TLS, or serve TLS directly

Example env file (paths, not secret values):

```sh
REFERENCE_ORIGIN=https://notebook.example.com
REFERENCE_CORE_URL=https://dsh.example.com
REFERENCE_CORE_CA_FILE=/run/secrets/core-ca.crt
REFERENCE_CORE_TOKEN_FILE=/run/secrets/app-token
REFERENCE_APPLICATION_ID=<registered UUID>
REFERENCE_CUSTOMERS_FILE=/run/secrets/customers.json
REFERENCE_CALLBACK_SECRET_FILE=/run/secrets/callback-secret
REFERENCE_DB=/data/reference.sqlite3
REFERENCE_RETENTION_DAYS=7
REFERENCE_BIND=127.0.0.1
REFERENCE_PORT=8088
REFERENCE_TLS_REVERSE_PROXY=true
```

Omit `REFERENCE_CORE_CA_FILE` to use normal system CAs; no TLS verification bypass exists. Omit callback-secret configuration for polling-only operation. With the loopback configuration, a **local TLS reverse proxy** must forward HTTPS to `127.0.0.1:8088`, preserve the public Host header and bound incoming body/time limits. Non-loopback plain HTTP is rejected. Forwarded headers do not establish identity or origin. Cookies remain Secure even on the private proxy hop.

For direct TLS set `REFERENCE_BIND=0.0.0.0`, `REFERENCE_TLS_CERT=/run/secrets/notebook.crt` and `REFERENCE_TLS_KEY=/run/secrets/notebook.key`; do not use `REFERENCE_TLS_REVERSE_PROXY`. Use the provided Dockerfile with a declared `/data` writable volume and read-only secret files, no host root or Docker socket. Container runs as 65532; provision readable secrets and a volume owned by that UID. Explicitly publish the chosen HTTPS port. A host-loopback proxy configuration is not a cross-container plaintext shortcut.

Run with operator-managed environment, for example:

```sh
set -a
. /private/notebook.env
set +a
python3 app.py
```

Keep environment files private and never source untrusted files. The Dockerfile pins the same Python base family as the qualified Memory component, and installs no dependencies. Add memory/CPU/PID caps in deployment. Server allows 24 concurrent connections, 128 KiB request bodies, 15-second socket timeouts and 12-second Core transport deadlines. CSP forbids inline scripts, iframes and arbitrary connection destinations. Source/result text is rendered with `textContent`, not HTML.

## Workflow, retries and privacy

- Ask which domains RFC2606 reserves. Research retrieves only the sources granted by the operator. Answers show governed quotes, source URLs, retrieval time and uncertainty; this app contains **no canned research answer**.
- Answer may reuse knowledge; refresh retrieves again; correction requires a previous completed request owned by this customer. A correction is not a licence to overwrite canonical knowledge; Core’s evidence and promotion policy decides.
- The local SQLite submission is committed before contacting Core. Lost Core responses retry only `reference:<local-request-UUID>` with the identical payload. Browser retries retain their key while the page remains open; after page loss check the persisted request list before issuing another request.
- At most 32 unsettled app requests and 100 non-deleted records per customer. Five consecutive failed transport attempts pause visibly. Polling is bounded to 120 transport cycles at ten-second intervals (plus queue delay), then pauses visibly. The UI retry button resumes the same durable request, never creates a new inference request. Core has its own bounded budgets.
- Signed callbacks validate HMAC over `timestamp + '.' + deliveryId + '.' + exact body`, freshness within five minutes, application/subject/known receipt and size. Delivery tombstone and result effect commit in the same SQLite transaction before ACK. Conflicting IDs/results reject. Unknown receipt callbacks reject until admission response is reconciled; Core retries delivery without rerunning inference.
- Customer export includes the app’s conversation/result plus owned Core exports. One failed Core export fails the whole export rather than silently claiming completeness.
- Delete marks requests for coordinated cancellation/settlement, Core deletion and native/Memory owner cleanup. Local question/result are scrubbed **only after Core reports deleted**. Seven-day default retention uses the same path; unavailable owners leave visible retained/pending data, never silent disappearance. Delete newest dependent requests first when Core reports dependency blocking; the queue is fair and retries are bounded.
- Application/customer bindings, local IDs, payload digests, result digests and delivery-ID tombstones are retained as minimal anti-replay evidence. Signed stale callbacks cannot resurrect deleted content. Application live-store logical erasure is not physical media erasure; SQLite secure_delete is enabled. Backups must have an operator-defined encrypted retention/expiry policy; expiry is not verified by the app.
- The app is one process/SQLite owner with multiple request threads. Multi-replica SQLite or shared-volume deployment is not qualified. No background workflow scheduler, framework credentials, model selector or customer-controlled tool configuration is added.

## Tests

```sh
python3 -m unittest -v test_app
node --check static/app.js
```

The tests use temporary SQLite files, a real loopback HTTP server and an explicitly mocked Core. They exercise authentication, CSRF, idempotency after lost responses/restarts, customer binding, callbacks/replay/conflicts, coordinated deletion, retention, bounded polling and export. These are not provider/live research acceptance results.

## QA4 installed qualification

The real installed stack and Chromium UI passed. See
[Stage 3 as-built and boundaries](../docs/stage3/README.md).
The tested correction policy is conservative exact-quote revalidation; changed
quotes quarantine. Retention used explicit expired timestamps, not elapsed-day
soak. Live-store erasure does not erase backups or downloaded/exported artifacts.
