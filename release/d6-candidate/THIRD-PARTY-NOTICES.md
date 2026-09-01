# Third-Party Notices

ALICA Community DSH contains third-party software distributed under its respective licenses. This notice does not replace those licenses. Exact package inventories and detected license metadata are in the bundled CycloneDX SBOMs.

Principal components include Caddy, PostgreSQL, Keycloak, Docker/Compose interoperability material, Debian-derived runtime packages, Node.js dependencies, Python dependencies and Hermes Agent dependencies. Their upstream projects retain all rights and apply their own licenses. ALICA Ltd's EULA applies only to proprietary first-party binaries and materials and does not restrict third-party rights.

Operators can identify every executable image by the immutable digest in `manifest.json`, inspect the matching SBOM under `evidence/sbom/`, and review upstream license texts embedded in each OCI image/package. Unknown or incompatible license findings block publication.
