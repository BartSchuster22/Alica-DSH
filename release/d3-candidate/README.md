# ALICA Community DSH D3 candidate

Signed Minimum complete Cell candidate.

- Release: `rel_01a05cc2-1e38-76ce-82be-131617ccc196` / `1.0.0-d3.candidate.1`
- Manifest digest: `sha256:059a34ec192db0fbe5831077c2e29b0e9eb60033c4f50d7092cbcd3cb0b59744`
- UNIFY source: `cfa3b5f19574e14501488f23c277663002df79bb`
- alicactl digest: `sha256:aeefbc38902786d646728b6697a77161ed98258cec732b4c37fd58bfeb64d35f`
- Provider credential: create the root-owned mode `0600` file declared by `install-request.json`; it is copied to local Cell secret storage and is never written to public configuration.
- Scope: anchor AInbA lifecycle, deterministic report-only Doghouse, local BYOK, and no central runtime dependency.
- Not authorized: D4-D6.
