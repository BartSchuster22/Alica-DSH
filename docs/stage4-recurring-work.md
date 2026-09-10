# Bounded recurring work — Stage 4 operator contract

The external app authorizes a fixed recurring request; native Hermes owns its
schedule and durable workflow. Core continues to govern receipts, execution,
results, delivery and MemoryV4 promotion. This is not browser workflow management
or a general multi-tenant workflow API.

## Enable and authorize

Set `REFERENCE_NATIVE_PROJECT_ID` to the installed native project slug. Without
this explicit binding, recurring grant issuance is disabled. The existing TLS,
customer authentication, CSRF, Core service credential and callback setup remains
required; no Core credential is exposed through a recurring grant.

An authenticated customer may POST `/api/recurring` with:

```json
{"operation":"answer","question":"What does RFC 2606 reserve?","maxRuns":4,"minIntervalSeconds":60,"expiresInSeconds":3600}
```

The response includes `grantId` and a one-time bearer `token`. Treat this token as
a secret. It authorizes only this grant's fixed request, observation, and draining
cancellation. It cannot change the customer, question, operation or Core scope.
POST `/api/recurring/<grantId>/revoke` requires that customer's session and CSRF token.
Revocation prevents new admissions; existing admissions remain observable and
cancellable. Account deletion revokes grants and scrubs their request payloads.

## Bind the native owner

An installation operator places `workflow-policy.json` and `workflow-ca.crt` in
the native Hermes home. The policy has exactly `origin` (HTTPS app origin) and
`address` (operator-approved pinned IP). The CA must authenticate that hostname.
This binding is administrative configuration, never model-generated input.

Run `/opt/unify-adapter/application-runtime/workflow.py create` under the native
owner, with JSON on stdin. Required fields are `grantId`, `token`,
`intervalSeconds`, `timezone`, `maxRuns`, `estimatedUnitMicros`,
`maxEstimatedMicros`, and `noProgressSeconds`. Optional `dependsOn` must reference
a same-scope native workflow; `startAt` must be an offset-aware timestamp.
Use private files or a protected pipe, not shell arguments or checked-in JSON.

Other CLI actions are `status`, `tick`, `event`, and `cancel`; input contains `id`.
Explicit events use a stable `eventKey`. Normally Cron, not the operator, supplies
ticks. A kernel lock and native checkpoint CAS prevent overlapping owners.
General native workers cannot claim the restricted workflow card.

## Governed knowledge reuse

For known-context answers, the native reader evaluates complete governed quotes,
not arbitrary fragments from the surrounding page. It retains the original full
source provenance and rejects subquotes presented as canonical facts. Core and
MemoryV4 still own promotion, reuse, quarantine, and correction policy. Workflow
cards and cron output cannot promote facts or rewrite prompts, models, tools, or code.

## Policy and truthful outcomes

- Intervals are multiples of 60 elapsed seconds, up to a day. UTC occurrence keys
  avoid DST ambiguity; IANA timezone is for display. Calendar-cron is not supported.
- Missed slots coalesce; no catch-up burst. One active occurrence per workflow and
  at most eight live workflow cards per native home. App limits apply independently.
- Checkpoints precede dispatch. Lost responses reconcile the same app/event key.
- Dependencies wait without approval prompts. Backoff and no-progress limits stop
  unsuccessful work explicitly. An unknown outcome is not labelled successful.
- Cancellation drains through the app/Core owner, including logical request erasure.
- Estimated budget reservations are not provider billing. Absent provider cost is
  `null`, not zero.
- Models have no workflow-policy/configuration editing capability. Learning uses
  the existing validated Core/Memory path, not unrestricted self-modification.

Terminal settled workflows pause their native Cron job and remove their native
capability file. An exception with unresolved effects retains the capability for
operator reconciliation; do not blindly recreate it. Native workflow audit cards
and checkpoint history are retained. This does not claim physical, backup, export,
or complete audit-history erasure.

See UNIFY `dsh/rebuild/stage4/CONTRACT-V1.md` and the PROJECT-ALICA Stage 4 closure
for exact acceptance scope, evidence and immutable publication references.
