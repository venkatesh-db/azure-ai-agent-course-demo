# Day 2 Demo — Tools & Enterprise Process Automation

Mapped to the syllabus's Day 2 labs. Status per file below is honest: what
actually ran live against your Azure resources vs. what's written but not
executed.

## Setup

```bash
cd azure-agent-demo-setup
source .venv/bin/activate   # created in Day 1 setup
pip install -r day2/requirements.txt
cd day2
```

## Files and verified status

| File | Status | What it demonstrates |
|---|---|---|
| `tools_readonly.py` | ✅ Ran live | Mock backend for 3 read-only tools, covering all 6 test conditions from the syllabus's Lab 7 (valid, unknown service, invalid environment, timeout, empty response, malformed output, rate-limit) |
| `lab7_read_only_tools.py` | ✅ Ran live | Agent auto-selects and calls the right read-only tool per request; correctly reports every error condition instead of guessing. 6/7 test requests returned full answers; 1/7 hit an intermittent message-read-after-write lag (see note below) |
| `workflow.py` | ✅ Ran live (via lab9) | External state machine: valid/invalid transitions, single-use scoped approval tokens with expiry, persistence to disk |
| `tools_actions.py` | ✅ Ran live (via lab9 + lab10) | Write tools (`create_incident`, `request_service_restart`) enforcing idempotency-key + approval-token checks before doing anything |
| `lab9_approval_workflow.py` | ✅ Ran live, all 6 scenarios passed | Happy path, duplicate-action prevention, token-replay rejection, scope-mismatch rejection, invalid-transition rejection, pause/resume across a simulated process restart |
| `lab10_security_attacks.py` | ✅ Ran live | 5 social-engineering attacks against the agent ("I'm the VP", "skip approval, it's an emergency", a fabricated token, "use any token", a false-premise attack). All 5 refused at the model layer; the tool layer would have rejected them regardless (defense in depth) |
| `azure_function/function_app.py` | ✅ **Deployed and live-tested** | Real Azure Functions HTTP-triggered implementation of the same two write tools, live at `func-agent-demo-20674.azurewebsites.net`. Verified with real HTTP calls: approval-required rejection (403), successful creation (201/200), and idempotency-key replay returning the identical cached result instead of duplicating. |

## Run order

```bash
python3 lab7_read_only_tools.py
python3 lab9_approval_workflow.py
python3 lab10_security_attacks.py
```

`lab9` and `lab10` write `workflow_state.json` and `approval_tokens.json`
in this directory as their persistence layer — delete them between runs if
you want a clean slate (`rm workflow_state.json approval_tokens.json`).

## The one known flaky spot

In `lab7_read_only_tools.py`, one out of seven test requests occasionally
returns no reply text even after retries — reproducible, not consistent.
Root-caused to eventual-consistency lag between a run completing and its
final message being readable via `messages.list()`, most likely to surface
after multi-turn tool-calling exchanges. Mitigated with a short retry loop
(`get_agent_reply()`), which resolves it most of the time but not always.
Worth mentioning live if it happens — it's a genuine "production agents
have to handle eventual consistency" teaching moment, which is exactly
Day 3's theme.

## Design choice: Lab 9 runs the workflow directly, not through the LLM

The syllabus's Module 4 (workflow state) is a distinct topic from Module 2
(function calling) — the state machine and approval mechanics are what's
being taught, independent of whether an LLM or a person is driving them.
Driving `lab9`'s 6 scenarios directly through `workflow.py` makes every
assertion deterministic and fast to verify, rather than depending on how
an LLM happens to phrase tool calls on a given run. `lab10` is where the
LLM actually sits in front of these same tools, once the mechanics are
already trusted.
