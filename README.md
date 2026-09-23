# cidp-packages

Shared, non-deployable libraries for the Crypto Investment Decision Platform
(CIDP): the typed `bitso` adapter, shared Pydantic `models` matching the DB
schema, and a `common` module (retry/backoff decorator, etc.).

Published as versioned packages; every consumer repo pins an exact version —
never a floating reference.

Part of the CIDP polyrepo. See the umbrella repo `cidp-infra` for local
bring-up and shared CI workflows.

Status: bootstrap (V0, Task 0). The `bitso` adapter and `common` module land
in Task 2.
