# Algorithm Metadata Override via YAML Directory

## Context

Algorithm metadata is currently embedded in decorators. Operators want to
separate configuration from code so metadata can be updated without code
changes. A directory of YAML files is preferred to support multiple teams and
environments.

## Goals

- Load algorithm metadata overrides from a directory of YAML files.
- Use name/version/category/algorithm_type as non-overridable match keys.
- Allow other fields to be overridden when a match is found.
- Keep default behavior unchanged when no configuration is provided.

## Non-Goals

- Overriding the match keys.
- Changing algorithm registration mechanics or runtime execution.

## Configuration Format

Files use the `.algometa.yaml` suffix and contain a YAML list of entries.
Each entry must include match keys and may include override fields.

```yaml
- name: Prediction
  version: v1
  category: prediction
  algorithm_type: Prediction
  description: "Prediction algo (override)"
  created_time: "2026-02-01"
  author: "ml-team"
  application_scenarios: "demo,offline"
  extra:
    owner: "algo-core-service"
    priority: "high"
  logging:
    enabled: true
    log_input: false
    log_output: true
  execution:
    isolated_pool: true
    timeout_s: 120
```

## Matching and Override Rules

- Match keys: `name`, `version`, `category`, `algorithm_type`.
- Match keys are required and never overridden.
- If a match is found, the following fields may be overridden:
  `description`, `created_time`, `author`, `application_scenarios`, `extra`,
  `logging`, `execution`.
- Unmatched algorithms keep their decorator metadata.

## Load Behavior

- New `AlgorithmRegistry.load_config(path)` loads overrides.
- `path` points to a directory; only `*.algometa.yaml` are read.
- Files are processed in lexical order; entries are processed in file order.
- Later matches override earlier matches (deterministic precedence).
- Invalid entries are logged and skipped; loading continues.

## Integration

- Environment variable `ALGO_METADATA_CONFIG_DIR` supplies the directory.
- Service startup reads the env var and invokes `get_registry().load_config`.
- Overrides apply both to already-registered algorithms and future
  registrations.

## Error Handling

- YAML parse errors: warn and skip the file.
- Invalid entry schema: warn and skip the entry.
- Unknown override keys: warn and skip those keys.

## Testing

- Directory loading reads only `.algometa.yaml` files and applies ordering.
- Overrides apply after registration and before registration.
- Match keys remain unchanged even if provided as overrides.
- Invalid entries do not prevent other entries from loading.

## Rollout

- Default behavior unchanged without `ALGO_METADATA_CONFIG_DIR`.
- Operators can roll out metadata updates by editing YAML files only.
