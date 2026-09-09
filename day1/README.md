# Day 1 Demo — Agent Foundations & Enterprise RAG

Runnable, verified-working code for Day 1 of the course, mapped to the
syllabus's own lab numbers.

## Setup

```bash
cd azure-agent-demo-setup
python3 -m venv .venv && source .venv/bin/activate   # already created if you ran this earlier
pip install -r day1/requirements.txt
```

`.env` in the parent directory is already populated by `setup.sh`. `config.py`
loads it automatically.

## Run order

```bash
cd day1
python3 lab1_verify_environment.py       # smoke test: auth, model, latency/tokens
python3 lab2_incident_classifier.py      # basic agent, free-text responses
python3 lab3_structured_classifier.py    # schema-validated JSON output
python3 lab4_build_search_index.py       # embeds + indexes dataset/runbooks.json
python3 lab5_grounded_agent.py           # RAG: retrieval + grounded, citation-backed answers
```

Each lab creates its own agent and deletes it when done — safe to re-run
any of them independently (except Lab 5, which needs Lab 4's index to
already exist).

## What each lab demonstrates live

- **Lab 1**: proves the environment works before you're in front of a room.
- **Lab 2**: shows the agent asking clarifying questions on incomplete input
  (`"Something's broken"`) and refusing to remediate on security reports.
- **Lab 3**: schema-valid JSON on every normal case — and one instructive
  failure: the prompt-injection test case (`"Ignore your instructions..."`)
  causes the model to refuse in plain text, breaking the enforced schema.
  Good discussion point: `response_format` alone isn't a security boundary.
- **Lab 4**: builds a hybrid (keyword + vector) index over
  `dataset/runbooks.json`, which deliberately includes one obsolete runbook
  and one runbook with an embedded prompt-injection payload.
- **Lab 5**: the payoff demo. Retrieves real evidence, cites source IDs,
  correctly flags the obsolete document as superseded, and refuses to
  follow the injected "restart production now" instruction hidden inside a
  retrieved document — logging it as a security event instead.
  - Note: on 2 of 5 test questions, the model gave a bare "I cannot assist
    with that request" refusal rather than the "evidence insufficient"
    wording specified in the instructions. This is real, reproducible
    model behavior (not a bug in the code) — worth calling out live as an
    example of base-model safety heuristics overriding your prompt's
    explicit format, which is exactly the theme of Day 3's evaluation and
    adversarial-testing modules.

## Design choice: manual RAG instead of `AzureAISearchTool`

The Foundry SDK has a built-in `AzureAISearchTool` for agents, but wiring it
up requires pre-creating a Foundry "connection" resource pointing at Azure
AI Search — extra setup with no teaching payoff. This demo instead retrieves
from Search directly in Python and injects the results into the message as
an `EVIDENCE` block. It's more code, but it makes the RAG mechanism visible
line-by-line, which is more useful for teaching than a black-box tool call.

## Known model substitution

The original syllabus/course examples reference `gpt-4o-mini`, which Azure
has since deprecated. This demo uses `gpt-5-mini` (Generally Available)
instead — see `SETUP_LOG.md` in the parent directory for the full story.
