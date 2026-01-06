# HyperParams Registration Design

**Goal:** Remove decorator-level hyperparams configuration and infer hyperparams only from `run` signatures, enforcing `HyperParams` inheritance for consistent camelCase JSON.

**Architecture:**
- `DefaultAlgorithmDecorator` no longer accepts `hyperparams`.
- Hyperparams type is inferred from `run(self, req, params)` and must be a `HyperParams` subclass.
- `AlgorithmSpec.hyperparams_model` records the inferred model or stays `None` when no hyperparams are present.
- Registration fails fast with `AlgorithmValidationError` if the hyperparams type is not a `HyperParams` subclass.

**Tech Stack:** Python 3.11, Pydantic v2.

**Notes:**
- Hyperparams JSON schema and serialization use camelCase via `BaseModel` config inherited by `HyperParams`.
- Example algorithms remove `hyperparams=...` from `@Algorithm` and keep the `params: HyperParams` annotation in `run`.
