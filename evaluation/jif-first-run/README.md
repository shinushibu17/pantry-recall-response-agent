# First Jif agent evaluation

This folder preserves the first live result before remediation. It is deliberately
outside `outputs/`, so publishing the project later need not lose the failure.

- `protocol.json`: source, expectation, and implementation hashes frozen before
  the first live call. The original agent file is `agent-before-coverage-fix.py`.
- `agent-run.json`: original Bedrock trace. It called four tools but omitted
  `compare_scope`, so all ten comparisons remained unexecuted and status was
  INCOMPLETE_TOOL_COVERAGE. Its unverified prose wrongly called missing-lot stock
  affected; no tool finding or physical-action confirmation authorized that claim.
- `evaluation.json`: FAIL for the original live run. Offline scope expectations
  pass separately; unexecuted comparisons are not measured matching errors.
- `followup.json`: the transition from initial agent-held-out evaluation to
  regression use after inspecting feedback, including the later run's limits.

The new coverage continuation names missing tools and stock IDs, never expected
verdicts. It is bounded to one additional turn under the existing execution caps.
The later successful Jif run did not need the continuation; forced SDK tests cover
that failure path. Do not merge these attempts into a single passing held-out score.

Jif was never a blind deterministic-matcher test: the adapter was written against
its previously frozen, source-derived expectations. It is now also exposed to
agent-development feedback. Independent human label sign-off remains pending.
