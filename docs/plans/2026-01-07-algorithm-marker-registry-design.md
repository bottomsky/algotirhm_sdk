# Algorithm Marker + Registry Scan Design

## Context

The current decorator registers algorithms immediately, which makes it heavier
than desired. The goal is to make the decorator a thin marker that can live in
its own package while the registry handles loading and registration. Algorithms
are shared via a directory containing packages and a package-level `__all__`
list for exposure.

## Goals

- Keep the decorator as a lightweight marker (no registry side effects).
- Registry loads packages and registers algorithms based on `__all__`.
- Only `BaseAlgorithm` subclasses are accepted (no function algorithms).
- Support both `ALGO_MODULES` and `ALGO_MODULE_DIR` (merged load).

## Non-Goals

- Supporting function-based algorithms.
- Static AST scanning without imports.

## Proposed Design

### Decorator

- The decorator writes metadata to a class attribute (e.g. `__algo_meta__`).
- It does not call `AlgorithmRegistry.register`.
- It rejects non-`BaseAlgorithm` targets (warning/skip on registry side).

### Registry

- Add `load_packages_from_dir(path)`:
  - Add `path` to `sys.path` if not present.
  - Scan immediate subdirectories containing `__init__.py`.
  - Import each package and register items from its `__all__`.
- Add `register_from_module(module)`:
  - Read `__all__` and resolve each symbol.
  - Skip any object that is not a `BaseAlgorithm` subclass.
  - Skip if `__algo_meta__` is missing or invalid.
  - Build `AlgorithmSpec` from the metadata and class definition.

### Startup

- Continue to import `ALGO_MODULES` as today.
- If `ALGO_MODULE_DIR` is set, call `load_packages_from_dir`.
- After each import, call `register_from_module` to register exposed symbols.

## Error Handling

- Import failures: log warning and skip the package.
- Missing/empty `__all__`: log warning and skip.
- Non-`BaseAlgorithm` entries: warn and skip (no hard error).

## Testing

- Load from directory with packages and `__all__`.
- Ensure only `BaseAlgorithm` subclasses are registered.
- Confirm `__all__` exposure works and non-exposed classes are ignored.
- Confirm `ALGO_MODULES` and `ALGO_MODULE_DIR` both load.

## Rollout

- Update algorithm packages’ `__init__.py` to expose classes in `__all__`.
- Configure `ALGO_MODULE_DIR` for shared package loading.
