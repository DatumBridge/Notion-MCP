# ADR-0002

## Context

Notion MCP requires OAuth 2.0 authorization code with PKCE. The server supports dynamic client registration and refresh-token rotation.

## Decision

- Discover via RFC 9470 then RFC 8414
- Register a public client (`token_endpoint_auth_method=none`) unless DCR returns a secret
- Persist `client_id` (and secret if any) with the token grant
- Refresh under a process lock; treat `invalid_grant` as terminal
- Store tokens with `0600` permissions

## Alternatives Considered

1. Hard-coded client_id from a Notion public integration — extra operator setup; not required because DCR exists.
2. Client ID Metadata Document (CIMD) — supported by Notion but not needed for v1 local/Studio use.

## Consequences

Re-registering a new client orphans prior grants. Operators must reuse stored `client_id`.

## Trade-offs

+ Matches Notion's official client guide
+ Works for local CLI without a pre-registered app
− First-time connect needs a browser

## Risks

Concurrent refresh from multiple replicas can revoke the grant. v1 is single-process; do not share one refresh token across replicas without a lock.
