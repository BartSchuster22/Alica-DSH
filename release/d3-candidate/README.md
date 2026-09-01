# ALICA Community DSH D3 candidate

Signed Minimum complete Cell candidate.

- Release: `rel_01a05cd0-6350-716c-87fb-a18403f88213` / `1.0.0-d3.candidate.1`
- Manifest digest: `sha256:5888f0bb0ef5baf00a10330ab5e992ed67488efa5577f91c96313d5df21debfd`
- UNIFY source: `b729bb48dbd38567ca3d0994132581b42ecf3f8e`
- alicactl digest: `sha256:6677472304087d2e634f2edde4d88c5e4976dba36ccd58d8f0a346d0f7c42274`
- Provider credential: create the root-owned mode `0600` file declared by `install-request.json`; it is copied to local Cell secret storage and is never written to public configuration.
- Scope: anchor AInbA lifecycle, deterministic report-only Doghouse, local BYOK, and no central runtime dependency.
- Not authorized: D4-D6.
