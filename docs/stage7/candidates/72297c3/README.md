# Stage 7 QA4 corrected candidate — qualification pending

This immutable QA-only candidate replaces neither predecessor evidence nor its failed attempts. No Stage 7 or production PASS is granted by publication.

- **schema**: `stage7-core-correction-build/v1`
- **sourceRevision**: `72297c3d303c9278b9fb44f951e4050805c76885`
- **baseArchiveSha256**: `43a98d80cb49223e76be72b040913826552ba82cdd209e065d9e18162d4c68c6`
- **archive**: `dsh-stage7-qa4-72297c3-linux-amd64.tar.gz`
- **archiveSha256**: `26f98d6ffc8ecc576628b061a9851b8cd40e1e917f070a8567b9fb48ee969553`
- **releaseSha256**: `1486b3aa2dccb7a21941140508280b5125d816452e708e13c7640ea120a2e66c`
- **newCoreImage**: `sha256:86d47fdd52bf88cf8f91c9e2245ba6ebe69ed324955b9e157ebb676b83715f8a`

Only compiled `knowledge.js` and `service.js` overlay the pinned prior Core image. Remaining runtime images and deployment dependencies are unchanged; this is an observed assembly, not a reproducible full-source image-build claim. The original source excerpt, digest, metadata, timestamps and record identity are preserved while byte-identical reuse excerpts reference evidence already in the immutable plan. Input, stored-plan and result size limits remain unchanged. Deterministic size rejection settles as `GOVERNED_RESULT_LIMIT`, not endless pending. Legacy plans remain readable; application-image downgrade compatibility is not claimed.

Signature scope is QA; initial predecessor is zero and sequence is one. Externally pin trust SHA-256 `5af48e80bffa12df7921c2c688f4f2f2249c68032d04e6f7e10621668d264034` and verifier SHA-256 `62f39860a259a76721068b23140eca846def5acca5b728fbab26518576722547`. Verify all regular archive members, signatures and identities before executing installer code. Fresh installation uses root `/opt/dsh2-stage7-qa4` and cell `dsh2-stage7-qa4`; do not import earlier customer, owner or provider state as clean-install proof. No production routing, PSI integration, licence change, broader database migration or Stage 7.4–7.6 acceptance is authorized.
