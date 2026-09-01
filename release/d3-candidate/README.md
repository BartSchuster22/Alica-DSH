# ALICA Community DSH D3 candidate

Signed Minimum complete Cell candidate.

- Release: `rel_01a05cdf-5bb3-70d0-a4b9-1b71d61a3a63` / `1.0.0-d3.candidate.1`
- Manifest digest: `sha256:d4e3ab02254a040a9f77d1f87ead4d865e405f2b362f4e8fadfa1c0bd7037751`
- UNIFY source: `eca9c0afa598e0acf7114744faef805042d114b5`
- alicactl digest: `sha256:e080aa5a7646e0c3446260ec43c0af6af24385b103664e95c99f3a31b0267e23`
- Provider credential: create the root-owned mode `0600` file declared by `install-request.json`; it is copied to local Cell secret storage and is never written to public configuration.
- Scope: anchor AInbA lifecycle, deterministic report-only Doghouse, local BYOK, and no central runtime dependency.
- Not authorized: D4-D6.
