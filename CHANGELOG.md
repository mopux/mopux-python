# Changelog

All notable changes to `mopux` are documented here. The project follows [Semantic Versioning](https://semver.org/).

## Unreleased

- Verify incoming Mopux webhooks and parse signed events with typed access to task details and event data.

## 0.1.0 - 2026-11-22

First release.

- Sync (`Mopux`) and async (`AsyncMopux`) clients for the Mopux API v1 (spec 1.2.0): all 71 operations.
- Pydantic models generated from the OpenAPI spec, tolerant of unknown and missing fields.
- `Mopux.login()`, token functions and `with_token()`.
- `Page` with lazy `iter…()` helpers; accepts Laravel pagination, page fields and the plain lists of API 1.1.
- Typed errors, including `AuthorizationError.is_plan_restriction()` / `is_billing_blocked()` and `UncertainWriteError`.
- Retries for 429 and failed reads; writes are never retried.
- `Upload` for task documents and comment attachments; `MockApi` in `mopux.testing`.
