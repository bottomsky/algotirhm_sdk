# Registry Disable Switch for Remote Consul Queries

## Context

The service already supports in-memory algorithm registration and optional
Consul-based service registry. Operators may run the service in offline
environments and want local endpoints (for example `/service/info` and
`/algorithms`) to remain usable without attempting remote registry access.

## Goals

- Use a single environment switch to disable all remote registry behavior.
- When disabled, `/registry/algorithms` should return a clear, deterministic
  error rather than trying Consul.
- Keep local catalog endpoints working without any dependency on Consul.

## Non-Goals

- Provide a local fallback for `/registry/algorithms` when the registry is
  disabled.
- Add new registry backends or change the payload schema.

## Proposed Design

### Configuration

Continue using the existing `SERVICE_REGISTRY_ENABLED` flag. When false:
- The runtime hook `ServiceRegistryHook` is not installed (already true).
- No Consul registration, session renewal, or KV catalog publishing occurs.
- `/registry/algorithms` is short-circuited before any remote calls.

### HTTP Behavior

`GET /registry/algorithms`:
- If `SERVICE_REGISTRY_ENABLED=false`, return `api_error` with a stable status
  code and message (suggested: status 503, message "service registry disabled").
- If enabled, keep current behavior: fetch remote catalogs, aggregate, and
  return any registry errors as part of the response payload.

`GET /algorithms` and `GET /service/info`:
- Continue to use the in-memory algorithm registry and remain available when
  the registry is disabled.

### Error Handling

When disabled, avoid connection attempts and noisy Consul errors. The endpoint
returns a single, deterministic error response to clarify policy-based
unavailability. When enabled, existing error handling for Consul failures
remains intact.

## Testing

- Add a test that sets `SERVICE_REGISTRY_ENABLED=false`, calls
  `/registry/algorithms`, and asserts a deterministic disabled response without
  invoking the Consul client.
- Optional: integration test with `SERVICE_REGISTRY_ENABLED=true` to validate
  unchanged behavior.

## Rollout

No data migration is required. The change is backward compatible for users who
leave `SERVICE_REGISTRY_ENABLED=true`. Operators can disable the remote registry
in offline environments and still rely on local discovery endpoints.
