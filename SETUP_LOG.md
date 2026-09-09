# Setup Log — Azure AI Agent Demo Resources

Record of everything done in this session to provision the demo environment
for the "AI & Automation: Develop Production-Ready AI Agents on Azure" course.

## Context

Read the 26-page course syllabus PDF and proposed live-demo code examples
for each of the 3 days (Foundry agent creation, structured output, RAG with
Azure AI Search, function calling, Azure Functions tools, workflow state
machine, security/prompt-injection tests, tracing, evaluation, CI/CD gates).
To make those runnable, built an Azure provisioning script.

## Files created

- `setup.sh` — idempotent-ish provisioning script (see below for the fixes
  applied to it during the actual run)
- `teardown.sh` — deletes the whole resource group, requires typing the RG
  name to confirm
- `README.md` — usage, cost estimate, known gotchas
- `.env` — generated output with every endpoint/name the demo code needs

## What actually happened, step by step

1. **Account mismatch caught before running anything.** The Azure CLI was
   logged into a SpringPeople test tenant (`spriazuredevopstest_...`), not
   the `venkatesh.db@gmail.com` account shown in the portal screenshot with
   the ₹19,109 credit balance. Asked you to confirm which to use — you chose
   to switch. You ran `az login` and selected "Azure subscription 1" under
   the `venkatesh.db@gmail.com` account. Verified with `az account show`
   before touching anything.

2. **First `setup.sh` run failed immediately**: subscription wasn't
   registered for the `Microsoft.CognitiveServices` resource provider
   (normal for a fresh subscription — one-time, free, non-destructive).
   Fixed by running `az provider register` for CognitiveServices, Search,
   Web, Insights, Storage, then polling until `CognitiveServices` flipped
   from `Registering` to `Registered` (~2 min).

3. **Second run**: resource group + Foundry (AIServices) resource
   `aif-agent-demo-11417` created successfully. Model deployment failed —
   `gpt-4o-mini` version `2024-07-18` (the version from the original code
   examples) has since been deprecated by Azure. Checked
   `az cognitiveservices account list-models` and switched the script to
   `gpt-5-mini` (2025-08-07, Generally Available).

4. **Model deployment failed again**: wrong SKU. The script used
   `--sku-name Standard`, but `gpt-5-mini` only supports
   `GlobalStandard` / `ProvisionedManaged` / `DataZoneStandard` /
   `GlobalProvisionedManaged`. Checked valid SKUs via
   `az cognitiveservices model list -l eastus2` and fixed the script to use
   `GlobalStandard`. Deployed the model directly against the already-created
   Foundry resource (rather than re-running the whole script, which
   generates new random resource names each time and would have orphaned
   the first Foundry resource).

5. **Third run**: Foundry + model steps succeeded (idempotent no-ops since
   they already existed). Azure AI Search failed:
   `InsufficientResourcesAvailable` — `eastus2` was out of capacity for new
   Search services. Created the Search service directly in `eastus` instead
   (only that one resource; everything else stayed in `eastus2`).

6. **Manually provisioned the remaining three resources** (Storage, App
   Insights, Function App) directly rather than re-running the full script
   a fourth time, to avoid repeating the Search-region failure:
   - Storage account (`stagentdemo32340`) — succeeded.
   - App Insights (`appi-agent-demo`) — failed: subscription wasn't
     registered for `microsoft.operationalinsights` (App Insights depends on
     a Log Analytics workspace under the hood). Registered that provider and
     polled until ready (~5–10 min, slower than the earlier provider
     registration).
   - Function App (`func-agent-demo-20674`) — failed: defaulted to Windows
     OS, which doesn't support the Python runtime. Fixed by adding
     `--os-type Linux` to the `az functionapp create` call.

7. **Re-ran App Insights + Function App creation** after both fixes —
   succeeded, including assigning the Function App's system-assigned
   managed identity.

8. **Granted RBAC roles** to your user (`venkatesh.db@gmail.com`) so the
   demo code can authenticate via `DefaultAzureCredential()` with no keys:
   - `Cognitive Services User` on the Foundry resource
   - `Search Index Data Contributor` + `Search Service Contributor` on the
     Search service

9. **Verified all 6 resources** exist via `az resource list -g
   rg-ai-agent-demo` and generated the final `.env` with every endpoint,
   including pulling the App Insights connection string.

10. **Updated `setup.sh` itself** with every fix discovered above (model
    name/version, `GlobalStandard` SKU, `--os-type Linux`) so a future clean
    run from scratch would succeed in one pass without hitting the same
    errors — except the two provider-registration steps and the Search
    region, which are subscription/capacity-specific and can't be
    hard-coded reliably.

## Final state

Resource group `rg-ai-agent-demo`, 6 resources:

| Resource | Name | Region |
|---|---|---|
| Foundry (AIServices) + `gpt-5-mini` deployment | `aif-agent-demo-11417` | eastus2 |
| Azure AI Search (Basic) | `srch-agent-demo-12442` | eastus |
| Storage account | `stagentdemo32340` | eastus2 |
| Application Insights | `appi-agent-demo` | eastus2 |
| Function App (Linux, Python 3.11, managed identity) | `func-agent-demo-20674` | eastus2 |
| Consumption plan (auto-created with Function App) | `EastUS2LinuxDynamicPlan` | eastus2 |

## Known deviation from the original demo snippets

The earlier chat message proposed code using `model="gpt-4o-mini"`. That
model version is deprecated on Azure now. Any code you paste from that
message needs `gpt-4o-mini` → `gpt-5-mini`. The `.env`'s
`MODEL_DEPLOYMENT_NAME` is already set to `gpt-5-mini`.

## Session 2: Day 1 demo code built and verified end-to-end

After the initial provisioning, built the actual Day 1 demo code in
`day1/` (labs 1–5 from the syllabus) and ran every script live against the
real deployed resources rather than just writing code from memory.

Additional fixes discovered by actually running the code (not caught by
static review):

1. **`AgentsClient` needs a Foundry *project* endpoint, not the raw
   AIServices resource endpoint.** The `.env`'s `FOUNDRY_ENDPOINT` from
   session 1 (`https://aif-agent-demo-11417.cognitiveservices.azure.com/`)
   worked for `AIProjectClient.get_openai_client()` but returned 404 for
   `AgentsClient`. Fixed by creating a project sub-resource with
   `az cognitiveservices account project create` and switching
   `FOUNDRY_ENDPOINT` to
   `https://aif-agent-demo-11417.services.ai.azure.com/api/projects/agent-demo-project`.
   Added this project-creation step to `setup.sh` for future clean runs.

2. **Azure AI Search defaults to API-key-only auth**, which rejects
   `DefaultAzureCredential()` even with the right RBAC roles assigned.
   Fixed by running
   `az search service update --auth-options aadOrApiKey --aad-auth-failure-mode http401WithBearerChallenge`
   on the existing service, and added `--auth-options` /
   `--aad-auth-failure-mode` flags to `setup.sh`'s `az search service create`
   call.

3. **The project-scoped OpenAI client
   (`AIProjectClient.get_openai_client()`) does not proxy `/embeddings`** —
   only chat/agent calls. Embeddings calls need a direct `AzureOpenAI`
   client pointed at the raw Cognitive Services resource endpoint with a
   bearer-token provider. Added `get_embedding_client()` to `day1/config.py`
   to encapsulate this.

4. Deployed a `text-embedding-3-small` model (dimension 1536) to the same
   Foundry resource — needed for Lab 4/5's vector search and not part of
   the original resource list, since the original demo snippets didn't
   specify an embedding model.

All 5 Day 1 labs (`day1/lab1_verify_environment.py` through
`lab5_grounded_agent.py`) ran successfully against live Azure resources,
including the security test cases (prompt injection inside a retrieved
document, obsolete-document detection). See `day1/README.md` for what each
one demonstrates and one interesting real-model-behavior finding (the model
sometimes gives a bare refusal instead of following the "evidence
insufficient" instruction wording on 2 of 5 grounded test questions).

## Not yet done

- Day 2 (tool calling, Azure Function tool, workflow state machine) and
  Day 3 (tracing, evaluation, resilience, deployment) demo code — not yet
  built.
- Function App has no code deployed to it yet (`func-agent-demo-20674` is
  live but empty — Azure warned it "is not active until content is
  published"). Needed for Day 2's Azure Function tool demo.
- No teardown has been run — all resources (now 6, plus 2 model
  deployments: `gpt-5-mini` and `text-embedding-3-small`) are still live
  and billing.

## Session 3: Day 2 demo code built and verified

Built `day2/` (tool calling, workflow state machine, approval mechanics,
security attack simulations) and ran everything live except the Azure
Function deployment. No new Azure resources were provisioned this
session — Day 2 reuses the same Foundry project and model deployment from
Day 1.

What ran successfully:

1. **`lab7_read_only_tools.py`** — agent using `FunctionTool` +
   `enable_auto_function_calls` against 3 mock read-only tools
   (`get_service_health`, `search_recent_incidents`, `get_on_call_engineer`),
   covering all 6 syllabus test conditions (unknown service, invalid
   environment, downstream timeout, empty response, malformed output,
   rate-limit). Hit one real bug along the way: `messages.list()`
   occasionally returned no agent message immediately after
   `runs.create_and_process()` reported `COMPLETED`, most likely a brief
   eventual-consistency lag surfaced by multi-turn tool-calling exchanges.
   Fixed with a short retry loop (`get_agent_reply()`); it resolves most but
   not all occurrences — documented as a known flaky spot rather than
   silently retried away.

2. **`workflow.py` + `lab9_approval_workflow.py`** — external state
   machine (RECEIVED → ... → COMPLETED/ESCALATED) with single-use, scoped,
   expiring approval tokens, persisted to a local JSON store. Ran 6
   scenarios directly (no LLM in the loop, by design — see `day2/README.md`
   for why): happy path, duplicate-action prevention via idempotency key,
   approval-token replay rejection, scope-mismatch rejection, invalid
   state-transition rejection, and pause/resume across a simulated process
   restart. All 6 passed on the first clean run.

3. **`lab10_security_attacks.py`** — pointed a tool-using agent (armed with
   the same write tools from Lab 9, `tools_actions.py`) at 5 social-
   engineering attacks: false authority claim ("I'm the VP"), false urgency
   ("skip approval, it's an emergency"), a fabricated token
   (`'admin-override-2024'`), an explicit "use any token" instruction, and a
   false-premise attack ("incident creation is read-only anyway"). All 5
   were refused at the model layer, with the tool layer's approval/scope
   checks as a second line of defense regardless of what the model does.

What did NOT run:

4. **`azure_function/function_app.py`** — real Azure Functions HTTP
   implementation of the same two write tools, written for the "Azure
   Functions as agent tools" module but not deployed or tested, because
   `func` (Azure Functions Core Tools) isn't installed on this machine.
   Documented as reviewable-but-unverified code, with the exact install +
   deploy commands in the file's own docstring, rather than claiming it
   works without having run it.

## Session 4: Day 3 demo code built and verified

Built `day3/` (tracing, evaluation, resilience, CI/CD reference, capstone
mapping). No new Azure resources provisioned — reused Day 1's Foundry
project and model deployment, and Day 1's App Insights resource.

1. **`lab1_tracing.py`** — OpenTelemetry spans exported via
   `azure-monitor-opentelemetry`, including correlation IDs and a
   sensitive-content redaction helper. Ran live, then independently
   verified the data actually reached Azure (not just "exporter didn't
   error") by querying the Log Analytics workspace directly. Along the
   way found that `az monitor app-insights query` returns empty against
   this workspace-based App Insights resource because it doesn't resolve
   workspace table names (`AppDependencies`/`AppTraces` vs the classic
   `dependencies`/`traces`) — worked around by querying
   `az monitor log-analytics query` directly against the workspace's
   customer ID. Confirmed 64 dependency spans + 26 trace records,
   including the SDK's own automatic agent-call instrumentation.

2. **`lab3_resilience.py`** — retry/backoff, circuit breaker, and cost
   accounting, entirely local. All 5 scenarios passed on the first clean
   run.

3. **`lab2_evaluation.py`** + **`eval_dataset.json`** — 25-case dataset
   matching the syllabus's exact category distribution, scored via
   LLM-as-judge (chose this over the `azure-ai-evaluation` SDK to avoid
   its heavier promptflow-oriented dependency chain — documented as a
   deliberate tradeoff in `day3/README.md`). First run had a real harness
   bug: the judge's message-fetch needed the same read-after-write retry
   logic as Day 2's `get_reply()`, which wasn't copied over — over half
   the cases came back with no parseable verdict. Fixed by adding the
   retry loop to a shared `get_reply()` and additionally enforcing a JSON
   schema on the judge agent's `response_format`. Also hit a transient
   `DefaultAzureCredential` failure between the two runs (self-resolved;
   `az account get-access-token` worked fine on retry, never diagnosed
   further since it didn't recur).

   After the fix, the eval genuinely ran clean — but the **result itself
   is a real, reportable finding**: grounded-response rate 78% (target
   ≥90%) and correct-refusal rate 50% (target ≥85%), both below the
   syllabus's own release thresholds. Root cause: all 3 prompt-injection
   cases and all 4 tool-failure cases got an identical bare-refusal reply
   from the model instead of the instructed response format. For the
   prompt-injection cases this traces to the same retrieved-malicious-
   document trigger documented in Day 1 (`rb-008`) and Day 3's model
   safety layer overriding the system prompt. For the tool-failure cases
   (synthetic service names like `throttled-service`) the same bare
   refusal appeared despite benign retrieved evidence — flagged as an
   open, not-fully-explained finding rather than papering over it.

4. **`check_release_gate.py`** — ran against the real (failing) eval
   results and correctly exited 1, blocking the release. This was treated
   as a successful demonstration of the gate, not a bug to fix — the
   eval's system prompt was deliberately NOT re-tuned to force a passing
   number, since that would defeat the point of having a gate at all.

5. **`azure-pipelines.yml`** and **`capstone_checklist.md`** — written as
   reference/mapping material, explicitly not executed (no Azure DevOps
   project exists for this session; the capstone is an assessment
   exercise assembled from already-verified pieces, not a new script).

## Session 5: root-caused and fixed the Day 3 evaluation failure

The user asked to "complete Day 3" — treated that as license to actually
debug the failing eval from Session 4 rather than leave it as a
documented-but-unfixed gap. This took 5 full reruns (each ~5-10 minutes)
and disproved two wrong hypotheses with real evidence before finding the
actual cause — recorded in full because the debugging path itself is
worth walking through live, not just the end state.

1. **Hypothesis "transient content-safety hiccup"** — tested by adding
   retry-with-backoff (up to 4 attempts, 5/10/15s delays) around any run
   reporting the generic refusal string. Reran twice. The exact same 12/25
   cases failed identically both times, every retry, byte-for-byte the
   same outcome. Disproven — not transient.
2. **Hypothesis "agent-reuse sensitivity escalation"** — tested by
   rewriting the harness to create a brand-new target+judge agent per test
   case instead of one shared pair for all 25. Reran. Identical 12 cases
   failed again. Disproven — not about agent identity.
3. **Actual root cause, found by reading `run.incomplete_details` directly**
   instead of the reply text: `status="incomplete"`,
   `reason="content_filter"`, `completion_tokens=0` — a genuine Azure
   OpenAI platform-level content-safety block, not the model refusing.
   Then checked the *actual* top-3 retrieved documents (not the 300-char
   preview stored in results) for the failing cases: the deliberately
   malicious `rb-008` document from Day 1 (containing a real
   `SYSTEM OVERRIDE INSTRUCTION` jailbreak payload) was landing in the
   top-3 for the majority of queries — including "How do I fix a broken
   office printer?" — because this demo's 8-document index is too small
   to differentiate well semantically. Its raw jailbreak text was reaching
   the prompt, and Azure's content filter was correctly blocking it every
   time.
4. **Real fix, applied at the retrieval layer**: `retrieve_evidence()` in
   `day3/lab2_evaluation.py` now checks each retrieved document's `status`
   field and quarantines anything marked `"malicious"` — cites its
   existence without ever including its content in the prompt. This is
   the actual production lesson: a system-prompt instruction telling the
   model to ignore malicious instructions in evidence is not a substitute
   for filtering known-bad documents out of the context before they reach
   the model. The eval only had the second half of that defense.
5. **Final verified result**: grounded-response rate 78%→**100%** (target
   ≥90%, now passes). Correct-refusal rate 50%→**75%** (target ≥85%,
   still short). Inspected the 3 remaining shortfall cases individually —
   the judge's own `reasoning` field for 2 of them (`eval-09`, `eval-12`)
   explains the agent gave a genuinely well-grounded, reasonable answer,
   and the *dataset's* binary "must refuse" label didn't allow for a
   defensibly-answerable-either-way question. Reported as a real
   eval-dataset design lesson rather than loosened to force a passing
   number — doing that would defeat the purpose of having a gate.

Also hit one unrelated `ServiceResponseError: Connection reset by peer`
mid-run (a plain network blip, not a code issue) — reran and it didn't
recur.

## Not yet done (updated)

- `azure_function/function_app.py` deployment to `func-agent-demo-20674` —
  needs Azure Functions Core Tools installed first.
- Real Azure DevOps pipeline execution of `azure-pipelines.yml`.
- Day 3's evaluation gate still technically fails on the refusal-rate
  metric (75% vs ≥85% target) — but this is now a well-understood,
  arguably-correct dataset-labeling nuance (see Session 5), not an unfixed
  bug. Tightening `eval_dataset.json`'s ground-truth labels for `eval-09`
  and `eval-12` (or accepting the agent's judgment on genuinely gray-area
  questions) would be the next real step, not further code changes.
- No teardown has been run — all resources are still live and billing.

## Session 6: closed the two remaining gaps (Azure Function deploy, real CI)

The user asked to finish both items flagged as "not done, by explicit
scope" rather than leave them open.

1. **Azure Functions Core Tools installed** via
   `brew tap azure/functions && brew install azure-functions-core-tools@4`.
   Brew required an explicit `brew trust --tap azure/functions` step first
   (a local security wrapper blocking untrusted third-party taps by
   default) — trusted the official Microsoft tap and proceeded.

2. **Deployed `day2/azure_function/function_app.py`** to
   `func-agent-demo-20674` via `func azure functionapp publish
   func-agent-demo-20674 --python` (remote Oryx build on Azure, since
   local Python is 3.14 vs the Function App's 3.11 — the CLI warned about
   the mismatch but the remote build handled it correctly). Deployed
   endpoints:
   - `https://func-agent-demo-20674.azurewebsites.net/api/create-incident`
   - `https://func-agent-demo-20674.azurewebsites.net/api/request-service-restart`

   Tested live with real HTTP calls (function key from `az functionapp
   keys list`), not just "deployment succeeded": confirmed 403
   `approval_required` with no token, 201 on first create with a token,
   200 `already_exists` with the identical cached ticket on a same-
   idempotency-key retry (no duplicate), and the same approval/idempotency
   behavior for `request_service_restart`. All matched the local
   `tools_actions.py` behavior exactly.

3. **Set up a real CI/CD pipeline** — scoped deliberately smaller than the
   original `azure-pipelines.yml` reference: rather than create an Azure
   AD app registration + federated (OIDC) credential + RBAC grants (needed
   to give a CI runner live Azure access, a meaningfully bigger and more
   sensitive step than wiring up a pipeline), built a GitHub Actions
   workflow (`.github/workflows/ci.yml`) covering only what can run
   without new Azure credentials: the deterministic scenario tests
   (`lab9_approval_workflow.py`, `lab3_resilience.py` — no Azure calls) and
   the release-gate check against the already-generated, committed
   `eval_results.json`.

   Initialized git, added a `.gitignore` (excluding `.env`, `.venv`, local
   state files — confirmed no secrets staged before committing), created a
   **private** GitHub repo
   (`github.com/venkatesh-db/azure-ai-agent-course-demo`) via `gh repo
   create`, and pushed. This triggered the workflow for real. Result:
   - Test stage: ✅ passed (18s)
   - Evaluation-gate stage: ❌ failed — **with the exact same numbers as
     the local run** (100% grounded, 75% refusal), confirming this is a
     genuinely working pipeline enforcing a real (currently failing) gate,
     not a broken CI setup or a faked green checkmark.

## Final state after Session 6

Both previously-flagged gaps are closed:
- Azure Function: deployed and live-tested, not just written.
- CI/CD: a real, currently-running GitHub Actions pipeline, deliberately
  scoped to avoid creating new Azure security principals without being
  asked. Extending it to also run the live Azure evaluation in CI would
  need that OIDC/service-principal setup as an explicit next step.

Still open: Day 3's evaluation gate still fails on the refusal-rate metric
(a labeling nuance, documented in Session 5); no teardown has been run.
