# Final Production Capstone — Checklist

The syllabus's capstone scenario (a payment platform under load: 12,000
TPS incoming vs 4,000 TPS downstream capacity, P95 latency 500ms -> 3s,
20% timeout rate, DB pool saturation, Redis pressure, retry amplification,
duplicate Kafka events) is an assessment exercise, not a single script —
participants assemble it from the pieces already built across Day 1-3.
This checklist maps every capstone requirement to the file that already
proves that capability works, so a live capstone walkthrough can point at
real, previously-run code instead of building from scratch under time
pressure.

## Agent responsibilities -> proof it already works

| Capstone requirement | Proven by |
|---|---|
| Classify the incident | [day1/lab3_structured_classifier.py](../day1/lab3_structured_classifier.py) — schema-valid JSON classification |
| Retrieve approved runbooks | [day1/lab5_grounded_agent.py](../day1/lab5_grounded_agent.py) — hybrid retrieval + citations |
| Query service health | [day2/lab7_read_only_tools.py](../day2/lab7_read_only_tools.py) — `get_service_health` tool |
| Search previous incidents | [day2/lab7_read_only_tools.py](../day2/lab7_read_only_tools.py) — `search_recent_incidents` tool |
| Identify missing evidence | [day1/lab3_structured_classifier.py](../day1/lab3_structured_classifier.py) — `missing_information` schema field |
| Rank possible causes | [day1/lab5_grounded_agent.py](../day1/lab5_grounded_agent.py) — the INC-4821 example answer already reasons about pool saturation + retry amplification, the capstone's exact failure mode |
| Recommend safe actions | [day1/lab5_grounded_agent.py](../day1/lab5_grounded_agent.py) instructions layer |
| Handle a tool timeout | [day2/tools_readonly.py](../day2/tools_readonly.py) `slow-service` case + [day3/lab3_resilience.py](lab3_resilience.py) retry/circuit-breaker |
| Request approval | [day2/workflow.py](../day2/workflow.py) + [day2/lab9_approval_workflow.py](../day2/lab9_approval_workflow.py) |
| Create an incident ticket | [day2/tools_actions.py](../day2/tools_actions.py) `create_incident` |
| Prevent duplicate actions | [day2/lab9_approval_workflow.py](../day2/lab9_approval_workflow.py) Scenario 2 (idempotency keys) — directly answers the capstone's "duplicate Kafka events" failure mode |
| Generate an audit trail | [day2/workflow.py](../day2/workflow.py) `Workflow.audit_log` |
| Pass security tests | [day2/lab10_security_attacks.py](../day2/lab10_security_attacks.py) — 5/5 social-engineering attacks refused |
| Pass evaluation thresholds | [day3/lab2_evaluation.py](lab2_evaluation.py) + [day3/check_release_gate.py](check_release_gate.py) |
| Produce deployment evidence | [day3/azure-pipelines.yml](azure-pipelines.yml) (reference; not executed — see day3/README.md) |

## Capstone-specific gap: retry amplification / duplicate Kafka events

The capstone scenario explicitly calls out "retry amplification" and
"duplicate Kafka events" as root causes — this is the same failure mode
Day 1's `rb-006` (previous incident report) and Day 2's idempotency-key
design already address, but nothing in this repo simulates a message
queue directly. If demonstrating this live, the honest framing is:
"idempotency keys are the general defense against duplicate-event
amplification regardless of whether the trigger is a Kafka retry, an HTTP
retry, or an LLM re-asking for the same tool call" — point at
`lab9_approval_workflow.py` Scenario 2 as the concrete, already-verified
proof of that defense, rather than claiming a Kafka simulation that
doesn't exist in this repo.

## What is genuinely NOT built or verified

- No live load-testing / traffic-spike simulation (12,000 TPS etc.) — the
  capstone's numbers are a narrative prompt for discussion and
  architecture reasoning, not something this local demo environment can
  or should attempt to reproduce.
- Canary deployment and rollback in `azure-pipelines.yml` are placeholder
  `echo` steps, not real Azure DevOps automation — see day3/README.md for
  why.
- The Azure Function tool from Day 2 is written but not deployed.

Be upfront about these three gaps if walking through the capstone live —
everything else in the table above has actually been run against live
Azure resources in this session.
