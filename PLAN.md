<!-- /autoplan restore point: /home/dy/.gstack/projects/stt_test/main-autoplan-restore-20260331-105829.md -->
# Plan: User-Input-Driven Application Control Addon

## Plan Summary
Build a browser-based addon that turns user voice input into safe, auditable actions inside a target web application. The current repo already proves microphone capture, FastAPI upload, Korean STT, and one hard-coded browser action. This plan turns that fragile demo into a constrained automation system with explicit intents, confirmation, execution boundaries, and logs.

## Product Goal
- Let a user control a web application with natural Korean voice commands.
- Translate free-form speech into a small set of allowed actions such as open login, navigate, click a known control, or fill a known field.
- Keep humans in control with confirmation and visible feedback before risky actions.

## Product Boundary
- In scope: browser-based addon for web applications, using the current web recorder plus FastAPI backend.
- Out of scope: native desktop automation, arbitrary screen scraping, unrestricted DOM scripting on any site, background actions without a visible target tab, and full agentic browsing.

## Premises To Confirm
- The target application is primarily a web app running in the browser, not a native desktop app.
- The first supported commands can be restricted to a narrow allowlist instead of open-ended "do anything" automation.
- Korean speech recognition is the default language for MVP.
- Human confirmation before execution is acceptable for high-risk actions.

## Phase 1: CEO Review

### 0A. Premise Challenge
Premise 1, "addon" means browser extension, is reasonable because the current code already lives in the browser and opens URLs with `webbrowser.open`. If the real target is a native Windows or macOS app, this plan is wrong at the foundation and should be replaced with an OS automation architecture.

Premise 2, "free-form user input can directly manipulate the app," is too dangerous if interpreted literally. The plan narrows that into "free-form input is allowed at the front door, but execution only happens through a typed intent registry with argument validation."

Premise 3, "one-step voice command execution is good UX," is only half true. It is good for low-risk navigation, but foolish for destructive or account-changing actions. The system needs a confirmation ladder.

Decision: keep the browser-addon premise, reject unrestricted execution, add risk-tiered confirmation.

### 0B. Existing Code Leverage Map
| Sub-problem | Existing code | Reuse verdict | Gap |
|---|---|---|---|
| Audio capture in browser | `index.html` uses `navigator.mediaDevices.getUserMedia` and `MediaRecorder` | Reuse conceptually | Needs separation from demo UI and better error states |
| Upload audio blob to backend | `index.html` posts to `/upload-audio/` | Reuse path pattern | Needs API versioning and richer response schema |
| STT transcription | `back.py` calls Groq Whisper | Reuse provider integration | Needs isolation behind service boundary and retries |
| Backend web serving | `back.py` serves `index.html` through FastAPI | Reuse runtime | Needs extension-facing API, auth, and logging |
| Action execution | `back.py` substring-matches `"로그인"` and opens fixed URL | Do not reuse directly | Replace with typed intent pipeline and addon bridge |

### 0C. Dream State Diagram
```text
CURRENT
Browser button -> record audio -> upload blob -> Whisper transcript
-> if transcript contains "로그인" -> open fixed URL

THIS PLAN
Browser addon UI -> capture voice/text -> backend STT/NLU
-> typed intent + validated arguments + confidence + risk tier
-> user confirmation when needed
-> addon content script/background bridge
-> execute whitelisted action in target app
-> structured result + audit log + retry guidance

12-MONTH IDEAL
Multi-app plugin registry -> local and remote execution adapters
-> per-app schemas and selectors -> replayable command history
-> policy engine -> eval suite -> admin-safe rollout controls
```

### 0C-bis. Implementation Alternatives
| Approach | Effort | Risk | Pros | Cons | Decision |
|---|---|---|---|---|---|
| A. Keep current FastAPI app, add browser extension bridge, typed action registry | Medium | Medium | Closest to existing code, fastest credible path, explicit control plane | Requires extension packaging and selector maintenance | Chosen |
| B. Pure browser extension, no backend, use in-browser STT/NLU only | Medium | High | Lower deployment complexity | Provider support, model quality, and secret handling get messy fast | Rejected |
| C. Native desktop automation agent | High | High | Broader control surface | Wrong repo, wrong blast radius, security story gets ugly immediately | Rejected |

### 0D. Mode-Specific Analysis
Mode: selective expansion. Expand enough to make the MVP safe and buildable, but do not turn this into a general-purpose computer-use agent.

Approved expansions in blast radius:
- Add explicit intent parsing and action registry.
- Add browser extension components.
- Add confirmation UI and execution logs.
- Add automated tests around parsing, policy, and API contracts.

Deferred expansions outside the blast radius:
- Native desktop control.
- Multi-app marketplace.
- Model provider abstraction beyond Groq.

### 0E. Temporal Interrogation
Hour 1: user can record speech, send it, and see a transcript plus predicted action.

Hour 6: addon can execute a tiny allowlist such as open login, focus search, and click a known login button inside one target app.

Day 2: confidence thresholds, confirmation modal, action logs, failure states, and tests exist. The system is still narrow, but no longer reckless.

6 months: if this works, the pressure will be to support more apps and more commands. That only stays sane if the command surface is declarative now.

### 0F. Mode Selection Confirmation
Selective expansion is correct. Reducing scope to "just improve the demo" leaves the dangerous hard-coded execution model in place. Expanding to desktop or multi-app orchestration is ocean-boiling.

### 0.5 CEO Dual Voices
Outside voices were not run in this autoplan pass. The tool policy for this session does not let me delegate to subagents without an explicit user request, and there is no verified `codex exec` run here. Continuing in single-reviewer mode.

#### CEO Dual Voices - Consensus Table
```text
CEO DUAL VOICES - CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   Yes     N/A     N/A
  2. Right problem to solve?           Yes     N/A     N/A
  3. Scope calibration correct?        Yes     N/A     N/A
  4. Alternatives sufficiently explored?Yes    N/A     N/A
  5. Competitive/market risks covered? Partial N/A     N/A
  6. 6-month trajectory sound?         Yes     N/A     N/A
═══════════════════════════════════════════════════════════════
CONFIRMED requires two voices. This pass is single-reviewer, so N/A is expected.
```

### CEO Section 1. User Problem
The real user problem is not "transcribe speech." That part is already commodity. The problem is "let me trigger app actions quickly without hunting through UI, while still trusting that the system will not do something stupid."

If this stays a transcript demo, users get a toy. If it becomes a bounded action system, users get leverage.

### CEO Section 2. Error & Rescue Registry
| Failure | User impact | Rescue |
|---|---|---|
| STT mishears command | Wrong action suggestion | Show transcript, top intent, and edit/retry affordance |
| Low confidence intent | User loses trust | Do not execute, ask clarifying follow-up |
| Selector changed in target app | Action silently fails | Surface actionable error, record selector mismatch, disable action |
| User says destructive command | Potentially harmful action | Require explicit confirmation or reject by policy |
| Backend unavailable | Dead button feeling | Local UI shows offline state and retry guidance |

### CEO Section 3. Failure Modes Registry
| Mode | Severity | Mitigation |
|---|---|---|
| Free-form command directly maps to arbitrary JS | Critical | Ban arbitrary execution, use typed action registry only |
| Per-site permissions too broad | High | Restrict manifest host permissions to named target domains |
| Hidden background execution | High | Require active tab + visible execution toast |
| No audit trail | Medium | Store command, intent, result, and timestamp |
| No fallback for ambiguous speech | Medium | Add clarification or safe rejection path |

### CEO Section 4. What Already Exists
- Browser microphone capture and upload loop in [`index.html`](/home/dy/src/stt_test/index.html).
- FastAPI server and Groq transcription integration in [`back.py`](/home/dy/src/stt_test/back.py).
- A minimal Python entrypoint in [`main.py`](/home/dy/src/stt_test/main.py), currently unused for the app flow.

### CEO Section 5. Competitive / Market Risk
Many teams stop at "AI can hear commands" and ship a demo that clicks one thing. That is not durable. The real moat, even for a small project, is trustworthy execution in a constrained environment, not the speech model itself.

The main risk is over-promising breadth before reliability exists. This plan deliberately optimizes for one target app plus a narrow command set.

### CEO Section 6. Scope Decisions
- Add browser extension architecture now. Approved.
- Add generic desktop automation now. Rejected.
- Add typed intent registry now. Approved.
- Add confirmation UI now. Approved.
- Add rich analytics dashboard now. Deferred.

### CEO Section 7. 6-Month Regret Check
The thing that will look foolish in 6 months is any code path that lets raw transcript text trigger side effects. It will block scaling, testing, and safety reviews.

The second regret would be binding app logic to raw CSS selectors without a registry or health checks. That turns every UI refresh in the target app into a production incident.

### CEO Section 8. NOT in Scope
- Native app manipulation.
- Unbounded prompt-driven task execution.
- Multi-language STT beyond Korean for MVP.
- Cross-app macro recording.

### CEO Section 9. Dream State Delta
This plan gets to "safe single-app actioning." It does not get to "general app copilot." That delta is acceptable. Shipping the first credible loop matters more than pretending to solve the whole category.

### CEO Section 10. Completion Summary
The strategy is sound if the browser-addon premise is right. The core move is replacing substring-triggered side effects with a validated command pipeline. The biggest open product risk is target-app ambiguity, because browser architecture is wrong if you actually need desktop automation.

## Phase 2: Design Review

### Design Scope
UI scope exists, but it is light. The primary UX surfaces are the recorder/command launcher, transcript review, confirmation prompt, action result toast, and permission/error states.

### Design Dual Voices
Outside design voices were not run. Continuing in single-reviewer mode.

#### Design Litmus Scorecard
| Dimension | Score | Notes |
|---|---:|---|
| Information hierarchy | 7/10 | Need transcript, predicted action, and confidence in one glance |
| State coverage | 5/10 | Loading, low-confidence, denied-permission, offline, and selector-failed states must be explicit |
| Specificity | 7/10 | Need named screens and interaction order, not just "show modal" |
| Accessibility | 6/10 | Voice app still needs keyboard control and readable status text |
| Responsive behavior | 6/10 | Extension popup size constraints must be planned |
| Feedback loop | 8/10 | Immediate transcript plus action preview is the right core loop |
| Trust / safety UX | 8/10 | Confirmation ladder is required and should be visible |

### Design Pass Findings
1. Popup flow needs a fixed sequence: listen -> transcript -> predicted action -> confirm/execute -> result. If those states overlap, the product feels haunted.
2. Error states cannot just be status text. The user needs specific recovery actions such as "grant mic permission," "retry transcription," or "open target tab."
3. The first version should prefer explicit labeled buttons and simple cards over clever chat UI. This is command tooling, not a fake assistant screen.

### Design Recommendation
Use a compact extension popup with three cards:
- Input card: microphone button, typed fallback input, recording state.
- Understanding card: transcript, confidence, parsed intent, editable arguments.
- Execution card: risk badge, confirm button, last result, and recent history.

### Design Completion Summary
The UX can be good without being fancy. What matters is trust, state clarity, and a visible line between "I heard you" and "I acted."

## Phase 3: Engineering Review

### Scope Challenge
The current codebase has no addon scaffolding, no typed models, no tests, and no separation between transport, transcription, and execution. That means the plan must add structure, not just patch `back.py`.

### Eng Dual Voices
Outside engineering voices were not run. Continuing in single-reviewer mode.

#### Eng Dual Voices - Consensus Table
```text
ENG DUAL VOICES - CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               Yes     N/A     N/A
  2. Test coverage sufficient?         Partial N/A     N/A
  3. Performance risks addressed?      Partial N/A     N/A
  4. Security threats covered?         Yes     N/A     N/A
  5. Error paths handled?              Partial N/A     N/A
  6. Deployment risk manageable?       Yes     N/A     N/A
═══════════════════════════════════════════════════════════════
```

### Proposed Architecture
```text
extension/popup
  -> records voice or accepts typed command
  -> sends command payload to backend API

backend/api
  -> stores request metadata
  -> transcribes audio if needed
  -> parses transcript into typed intent
  -> applies policy + confidence thresholds
  -> returns preview to popup

extension/background
  -> receives approved execution request
  -> locates active tab on allowed domain
  -> forwards action to content script

extension/content-script
  -> maps intent to DOM action handlers
  -> executes bounded action
  -> returns structured result

backend/logging
  -> stores transcript, intent, action, result, error code, timestamps
```

### File and Module Plan
| Path | Responsibility |
|---|---|
| `app/server.py` | FastAPI app factory and routes |
| `app/models.py` | Pydantic request/response and intent models |
| `app/stt.py` | Groq transcription adapter |
| `app/intents.py` | Intent parser, confidence thresholds, allowlist |
| `app/policy.py` | Risk tiers and confirmation rules |
| `app/logging.py` | Execution log write path |
| `extension/manifest.json` | Browser addon manifest with narrow host permissions |
| `extension/popup.html` `extension/popup.js` `extension/popup.css` | Popup UI and state machine |
| `extension/background.js` | Runtime messaging and tab targeting |
| `extension/content-script.js` | App-specific DOM action handlers |
| `tests/test_intents.py` | Parsing and policy tests |
| `tests/test_api.py` | API contract tests |
| `tests/test_extension_contract.md` | Manual verification checklist until extension automation exists |

### Code Quality Review
`back.py` currently mixes HTTP serving, file handling, transcription, business rules, and side effects in one route. That is fine for a demo and terrible for anything else. Split it before adding more branches.

The env var naming is also suspect: `Groq(api_key=os.environ["GROK"])` looks like a typo or footgun. The plan should normalize provider config and validate env vars at startup.

### Test Diagram
| Flow / Branch | Coverage needed | Proposed test |
|---|---|---|
| Audio upload succeeds | API contract | FastAPI route test with mocked STT |
| Audio upload unsupported / empty | Validation | API route negative tests |
| Transcript maps to known low-risk intent | Parser + policy | Unit test |
| Transcript maps to high-risk intent | Parser + confirmation | Unit test |
| Transcript ambiguous | Safe rejection | Unit test |
| Allowed-domain tab missing | Extension failure | Manual checklist first, later integration test |
| Selector missing in target app | Content script failure | Handler unit test + manual verification |
| Backend offline | Popup error state | Manual UI checklist |
| Permission denied for mic | Popup state | Manual UI checklist |

### Performance Review
The audio blobs are currently written to disk for every request. That is acceptable for MVP volumes, but the plan should set file size limits and delete temp files in `finally` blocks.

The expensive step is transcription, not DOM execution. Performance wins come from short recordings, early client-side stop, and avoiding retranscription loops when the user only edits text.

### Security Review
The biggest risk is letting model output directly choose DOM actions. The plan prevents that by making the model produce only an intent candidate, then validating it against a local allowlist.

The second risk is over-broad extension permissions. Restrict host permissions to the target domain and block execution on other tabs by default.

### Failure Modes Registry
| Failure | Severity | Engineering response |
|---|---|---|
| Temp file orphaned after exception | Medium | Use `try/finally` and temp directory cleanup |
| Invalid env var at boot | High | Startup validation with clear error |
| Action handler throws in content script | High | Structured error response and user-facing toast |
| Backend returns malformed intent payload | High | Pydantic response model and contract tests |
| Extension and backend schemas drift | Medium | Shared JSON schema or versioned contract file |

### What Already Exists
- FastAPI route structure and HTML serving in [`back.py`](/home/dy/src/stt_test/back.py).
- Browser audio capture loop in [`index.html`](/home/dy/src/stt_test/index.html).
- Dependency scaffold in [`pyproject.toml`](/home/dy/src/stt_test/pyproject.toml).

### Eng NOT in Scope
- Selenium or Playwright end-to-end extension automation in the first implementation pass.
- Distributed queueing, job orchestration, or streaming transcription.
- Multi-provider model routing.

### Implementation Phases
1. Refactor backend into `app/` modules and preserve current STT endpoint behavior.
2. Add typed intent parsing, policy tiers, and structured API responses.
3. Scaffold browser extension popup/background/content script for one allowed domain.
4. Add confirmation flow and execution logs.
5. Add tests for parser, policy, API contracts, and a manual extension checklist.

### Completion Summary
This plan is buildable. The hidden complexity lives in browser extension messaging, selector stability, and keeping model output on a short leash. If those boundaries are explicit, the rest is straightforward engineering.

## Cross-Phase Themes
- Trust boundary is the whole game. Product, UX, and engineering all independently point to the same requirement: model output cannot directly cause arbitrary side effects.
- Narrow scope is a feature, not a weakness. One app, one allowlist, one language, one visible confirmation loop.
- State clarity matters as much as model quality. Users need to see transcript, predicted action, and result.

## Final Recommended Plan
1. Keep FastAPI and Groq STT, but move them into explicit service modules.
2. Replace substring matching with `intent -> args -> risk tier -> allowed action`.
3. Build a browser extension for the target web app instead of opening URLs with Python.
4. Require confirmation for medium and high-risk actions.
5. Log every attempted action with transcript, parsed intent, target domain, and outcome.
6. Ship only a tiny allowlist for the first target app.

## Deferred To TODOS.md
- Multi-app support after one target app is stable.
- Desktop app automation if the real target is not browser-based.
- Additional languages after Korean MVP.
- Automated extension E2E after contract and manual flows stabilize.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Scope addon as browser-based, not desktop automation | User challenge candidate | Pragmatic | Matches current repo and avoids false architecture | Native desktop control now |
| 2 | CEO | Replace transcript substring matching with typed intent registry | Mechanical | Explicit over clever | Safer, testable, scalable | More hard-coded `if "word" in text` branches |
| 3 | CEO | Add confirmation ladder for risky actions | Mechanical | Choose completeness | Prevents wrong-action disasters | One-step execution for everything |
| 4 | CEO | Keep MVP to one target app and allowlist | Mechanical | Boil lakes | Completes one real loop instead of a fake broad platform | Multi-app generalized automation |
| 5 | Design | Use explicit popup cards instead of chat UI | Taste | Explicit over clever | Better trust and state clarity | Conversational assistant-style UI |
| 6 | Eng | Split `back.py` into modules before feature growth | Mechanical | Explicit over clever | Reduces coupling and enables testing | Keep monolith route and add branches |
| 7 | Eng | Add browser extension bridge | Mechanical | Choose completeness | Required for real in-app control | Continue using `webbrowser.open` side effects |
| 8 | Eng | Start with manual extension checklist before full E2E automation | Taste | Pragmatic | Enough for MVP without stalling the build | Immediate full browser automation suite |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | Browser-only premise must be confirmed; unrestricted execution rejected |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | Current monolithic route, missing extension architecture, no tests |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | issues_open | Missing state model, trust UX, and explicit confirmation flow |

**VERDICT:** REVIEWED PLAN READY. Premises still need user confirmation before implementation starts.
