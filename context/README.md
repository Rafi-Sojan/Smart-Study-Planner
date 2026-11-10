# Repository context index

The `context/` directory is the maintained entry point for agents and
contributors who need the project's operating constraints, current direction,
and durable decisions without reconstructing them from chat history.

## Reading order

1. Read `AGENTS.md` before taking any action. It is the authoritative merged
   operating guide.
2. Read `PROJECT_CONTEXT.md` to understand the product, evidence boundaries,
   architecture, and present release posture.
3. Read `PLANS.md` before starting or extending project work.
4. Consult `DECISIONS.md` before changing a durable data, model, interface,
   artifact, or release contract.
5. Follow links into `../docs/` for the complete formal specification of the
   subsystem being changed.

## Source-of-truth boundaries

- `context/` summarises working rules, direction, and decisions.
- `docs/` contains detailed formal documentation.
- Executed metrics and validation reports under `artifacts/` are the measured
  evidence.
- `dvc.yaml` and `dvc.lock` define generated data and artifact lineage.
- Code, tests, workflows, and deployment manifests define executable behaviour.

When these disagree, do not silently choose the most convenient version. Verify
the executable state, identify the stale document, and update the affected
sources together.

## Maintenance rules

- Keep one authoritative merged guide at `context/AGENTS.md`.
- Keep the root `AGENTS.md` as a discovery pointer only; do not add scoped rules
  there.
- Do not recreate nested `AGENTS.md` files. Add path-specific guidance to a
  clearly labelled section of the unified guide.
- Update `PLANS.md` when work changes state, but never mark an external action as
  complete without evidence.
- Add or amend a decision record when a durable contract changes.
- Never place secrets, tokens, row-level private data, or invented results in
  this directory.
