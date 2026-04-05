# Engineering Orchestration Workflow · v4.0
## Agile + V-Model Hybrid | Senior Multi-Role Architecture

> A precision-grade framework operated by four senior engineering roles working in full
> coordination. Every phase is iterative (Agile), every phase is verified and validated
> (V-Model). Clean architecture is non-negotiable — no spaghetti code, no shortcuts,
> no technical debt left unaddressed.

---

## I. Senior Role Definitions

These are not junior perspectives. Every decision, review, and output must meet
the standard of a seasoned senior engineer in that role. When prompting Claude,
invoke the role explicitly to get senior-grade thinking.

---

### 🧠 Senior Solution Architect
**Owns:** System vision, architectural integrity, non-functional requirements, technology decisions

**Responsibilities:**
- Defines the overall system design — services, boundaries, data flows, integration patterns
- Enforces clean architecture: separation of concerns, loose coupling, high cohesion
- Rejects spaghetti architecture — no tightly coupled modules, no god objects, no circular dependencies
- Signs off every major architectural decision before implementation begins
- Ensures the system is scalable, secure, observable, and maintainable from day one
- Applies established patterns: hexagonal architecture, domain-driven design, event-driven systems, microservices or monolith (chosen deliberately, not by default)
- Reviews architectural drift in every sprint — raises red flags immediately

**Non-negotiable standards:**
- Every component has a single, well-defined responsibility
- Interfaces are contracts — they never leak internal implementation details
- No architectural decisions made under sprint pressure without proper review
- If it can't be drawn cleanly on a whiteboard, it's too complex

**Senior Architect Claude Prompt:**
```
Act as a Senior Solution Architect with 15+ years of experience.
Review this system design: [DESIGN]

Evaluate:
1. Is the architecture clean — are boundaries, responsibilities, and contracts clear?
2. Where does coupling exist that should not? Fix it.
3. What non-functional risks exist (security, scalability, reliability, observability)?
4. What architectural patterns apply here and why?
5. What would you reject before a single line of code is written?
Be direct. Flag every weakness without softening.
```

---

### 💻 Senior Software Engineer
**Owns:** Code quality, module design, clean implementation, test coverage, technical standards

**Responsibilities:**
- Writes clean, maintainable, testable code — always
- Enforces SOLID principles on every module:
  - **S** — Single Responsibility: one reason to change
  - **O** — Open/Closed: open for extension, closed for modification
  - **L** — Liskov Substitution: subtypes must be substitutable
  - **I** — Interface Segregation: no fat interfaces
  - **D** — Dependency Inversion: depend on abstractions, not concretions
- Applies TDD (Test-Driven Development): tests before implementation, always
- Refuses to merge code that does not meet the Definition of Done
- Performs rigorous code reviews — questions every abstraction, every naming choice, every dependency
- Eliminates dead code, magic numbers, and undocumented workarounds immediately
- Escalates architectural concerns to the Senior Solution Architect rather than working around them

**Non-negotiable standards:**
- No function longer than 20–30 lines without justification
- No module with more than one clearly defined responsibility
- No merging without passing tests, code review, and CI pipeline green
- No TODO comments left in production code — they are either addressed or filed as formal backlog items

**Senior Software Engineer Claude Prompt:**
```
Act as a Senior Software Engineer with deep expertise in clean code and TDD.
Module: [MODULE NAME]
Design spec: [SPEC]

1. Apply SOLID principles to this module design. Where does it violate them?
2. Write the unit tests first (TDD). Cover all edge cases and failure paths.
3. Implement the code to pass the tests — clean, readable, no shortcuts.
4. Review your implementation: what would you reject in a code review?
5. What refactoring is needed before this is production-ready?
```

---

### ⚙️ Senior DevOps Engineer
**Owns:** CI/CD pipelines, deployment reliability, infrastructure automation, observability, incident response

**Responsibilities:**
- Designs and owns the full CI/CD pipeline — build, test, scan, deploy, monitor
- Enforces Infrastructure as Code (IaC) — every environment is version-controlled and reproducible
- Ensures every commit is automatically tested — no manual deployment steps
- Maintains zero-downtime deployment strategies: blue/green, canary, rolling
- Owns monitoring, alerting, and observability from day one — not as an afterthought
- Resolves failing pipelines and CI issues autonomously — does not wait for permission
- Applies the "Just Fix It" rule: bug reports and pipeline failures are commands, not discussions
- Ensures staging is always a production-mirror — no surprises on deployment day
- Owns security scanning in the pipeline: SAST, DAST, dependency vulnerability scanning

**Non-negotiable standards:**
- No manual deployments to any environment — everything is pipeline-driven
- No environment exists outside of IaC — if it's not in code, it doesn't exist
- No deployment without automated rollback capability
- No blind spots in observability — every service emits logs, metrics, and traces

**Senior DevOps Engineer Claude Prompt:**
```
Act as a Senior DevOps Engineer with deep expertise in CI/CD, IaC, and production reliability.
System: [SYSTEM NAME]
Stack: [TECH STACK]

1. Design the full CI/CD pipeline: build → test → security scan → deploy → monitor.
2. What IaC tooling and structure is required for this stack?
3. What is the zero-downtime deployment strategy?
4. What observability stack is needed (metrics, logs, traces, alerts)?
5. What are the top 3 failure modes in production and how do we detect and recover from each?
Be specific. No generic advice — give the actual implementation approach.
```

---

### 🏗️ Senior Platform Engineer
**Owns:** Internal developer platform, golden paths, environment consistency, self-service tooling, cognitive load reduction

**Responsibilities:**
- Builds and maintains the Internal Developer Platform (IDP) — the foundation every other role builds on
- Defines golden paths: pre-approved, tested, opinionated templates that work out of the box
- Ensures every environment (dev, staging, production) is consistent and reproducible
- Reduces developer cognitive load — engineers should focus on product, not infrastructure setup
- Implements GitOps-first workflows — the repository is the source of truth for all environments
- Enforces security by default — all golden paths embed security standards, no opt-in required
- Owns platform observability: every service deployed through the platform emits telemetry automatically
- Maintains the platform as a product — with a roadmap, user feedback loop, and documented APIs

**Non-negotiable standards:**
- No snowflake environments — every environment is provisioned from the same template
- No manual onboarding — a new engineer must be able to set up and deploy in under 30 minutes
- No platform changes without backward compatibility or a deprecation path
- Security, compliance, and observability are built-in — not bolted on

**Senior Platform Engineer Claude Prompt:**
```
Act as a Senior Platform Engineer with deep expertise in IDPs, GitOps, and developer experience.
Project: [PROJECT NAME]
Team size: [SIZE]
Stack: [TECH STACK]

1. Design the Internal Developer Platform structure for this project.
2. What golden path templates are needed — define them specifically.
3. How do we enforce environment consistency across dev, staging, and production?
4. What self-service capabilities reduce the most cognitive load for the Software Engineers?
5. Where does security need to be enforced by default in the platform?
```

---

## II. The Hybrid Model — Agile + V-Model

Every sprint is iterative (Agile). Every sprint has a paired verification or validation
layer (V-Model). You cannot separate the two.

```
V-MODEL PHASES (Left = Build, Right = Test)

  Requirements Analysis ──────────── User Acceptance Testing (UAT)
        ↓                                          ↑
  System Design ───────────────── System Testing
        ↓                                   ↑
  Architecture Design ──────── Integration Testing
        ↓                              ↑
  Module Design ──────── Unit Testing (TDD)
        ↓                     ↑
           [ CODE / IMPLEMENTATION ]

AGILE WRAPPER (Sprints run across every level above)

  Sprint 1 → Sprint 2 → Sprint 3 → ... → Sprint N
  ┌─────────────────────────────────────────────┐
  │  Plan → Build → Verify → Review → Refine   │
  │     ↑                              ↓        │
  │     └──── Backlog Refinement ←─────┘        │
  └─────────────────────────────────────────────┘
```

---

## III. The Six-Phase Delivery Cycle

---

### Phase 1 · DEFINE — Requirements Analysis
**Sprint Duration:** 1–2 sprints
**Lead Role:** Senior Solution Architect
**Supporting Roles:** Senior Software Engineer, Senior DevOps Engineer
**V-Model Pair:** Acceptance Testing criteria written here — UAT validates these at the end

**What must happen:**
- Define the problem in 1–3 clear, unambiguous sentences
- Capture all functional requirements — each must be testable and measurable
- Capture all non-functional requirements (performance SLAs, security standards, uptime, scalability targets)
- Write acceptance criteria per requirement — these become UAT test cases in Phase 6
- Senior Solution Architect identifies architectural constraints and technology boundaries
- Senior DevOps Engineer defines deployment, environment, and observability requirements
- All risks, unknowns, and external dependencies mapped

**Senior Architect Anti-Pattern Check:**
- Reject vague requirements — "fast", "scalable", "secure" must have numbers attached
- Reject scope that hasn't been decomposed — no single requirement should take more than one sprint to implement
- Flag any requirement that introduces implicit architectural coupling

**Phase 1 Quality Gate — Cannot proceed without:**
- [ ] All requirements documented with measurable acceptance criteria
- [ ] Non-functional requirements defined with quantified targets
- [ ] Risks and dependencies catalogued
- [ ] Senior Solution Architect has reviewed and approved requirements
- [ ] No ambiguous requirements remaining

**Claude Prompt:**
```
Act as a Senior Solution Architect.
Project: [NAME]
Problem: [PROBLEM]
Constraints: [CONSTRAINTS]

Document formal requirements with measurable acceptance criteria.
Flag any requirements that are vague, untestable, or architecturally risky.
Define non-functional requirements with specific, quantified targets.
What is missing before we can proceed to architecture design?
```

---

### Phase 2 · EXPLORE — Architecture & System Design
**Sprint Duration:** 1–2 sprints
**Lead Role:** Senior Solution Architect
**Supporting Roles:** Senior Platform Engineer, Senior DevOps Engineer
**V-Model Pair:** System Testing strategy defined here

**What must happen:**
- Design the full system architecture: services, boundaries, APIs, data flows, integrations
- Apply architectural patterns deliberately: hexagonal, event-driven, microservices, CQRS — chosen for the problem, not for trend
- Senior Platform Engineer designs environment topology and golden path templates
- Senior DevOps Engineer designs CI/CD pipeline architecture and observability stack
- Create design verification checklist — each component must have a corresponding test strategy
- Document all architectural decisions with rationale (Architecture Decision Records — ADRs)

**Senior Architect Anti-Pattern Check:**
- Reject any design with tightly coupled services sharing a database without justification
- Reject any design that cannot be drawn with clear boundaries and arrows
- Reject technology choices made without trade-off analysis
- Flag premature optimisation — don't design for 10x scale when you need 1x

**Phase 2 Quality Gate — Cannot proceed without:**
- [ ] Architecture diagram with clear component boundaries
- [ ] ADRs written for every significant design decision
- [ ] System test strategy documented per component
- [ ] CI/CD pipeline architecture finalised
- [ ] Deployment topology and environment strategy confirmed
- [ ] Senior Solution Architect sign-off

**Claude Prompt:**
```
Act as a Senior Solution Architect.
Requirements: [FROM PHASE 1]
Stack constraints: [CONSTRAINTS]

Design the system architecture.
For every design decision, document the trade-offs and rejected alternatives (ADR format).
Flag any design smell: tight coupling, shared state, unclear boundaries, premature optimisation.
What does the system test strategy look like for this architecture?
```

---

### Phase 3 · DESIGN — Module & Detailed Design
**Sprint Duration:** 1–2 sprints
**Lead Role:** Senior Software Engineer
**Supporting Roles:** Senior Solution Architect
**V-Model Pair:** Integration Testing strategy defined here

**What must happen:**
- Decompose system components into implementable modules
- Define interface contracts per module: inputs, outputs, error states — these are binding
- Define data structures and domain models
- Document integration points between modules
- Write integration test strategy based on module interfaces
- Senior Solution Architect reviews module design for architectural compliance

**Senior Software Engineer Anti-Pattern Check:**
- Reject fat interfaces — each interface should expose only what the consumer needs
- Reject modules with more than one responsibility
- Reject undefined error handling — every failure path must be designed, not discovered
- Flag any module that reaches directly into another module's internal state

**Phase 3 Quality Gate — Cannot proceed without:**
- [ ] Module interface contracts documented
- [ ] Data structures and domain models defined
- [ ] Integration test scenarios written per interface
- [ ] Module design reviewed against SOLID principles
- [ ] Senior Solution Architect architectural compliance sign-off

**Claude Prompt:**
```
Act as a Senior Software Engineer applying clean architecture and SOLID principles.
Component: [COMPONENT]
Architecture spec: [FROM PHASE 2]

Design the module in detail.
Define interface contracts (inputs, outputs, error states) — these are immutable once agreed.
Apply SOLID. Where does this design violate any principle?
Write the integration test scenarios for this module's interfaces.
What would you reject in a design review?
```

---

### Phase 4 · BUILD — Implementation + Unit Testing
**Sprint Duration:** 2–3 sprints (repeating per module)
**Lead Role:** Senior Software Engineer
**Supporting Roles:** Senior DevOps Engineer
**V-Model Pair:** Unit Testing — executed in the same sprint as implementation

**What must happen:**
- Write unit tests before implementation (TDD — no exceptions)
- Implement to the interface contract defined in Phase 3
- Every commit triggers the automated CI pipeline (Senior DevOps)
- Code review required before any merge — Senior Software Engineer reviews every PR
- Static analysis, linting, and security scanning run automatically

**Senior Software Engineer Anti-Pattern Check:**
- Reject any function longer than 30 lines without documented justification
- Reject magic numbers, magic strings — all constants are named and explained
- Reject incomplete error handling — happy path only is not acceptable
- Reject test code that only tests the happy path — edge cases and failures are mandatory
- Reject TODO comments — file a backlog item or fix it now

**Senior DevOps Anti-Pattern Check:**
- Reject any merge that breaks the CI pipeline
- Reject any merge without automated test results
- Reject any hardcoded credentials, environment values, or configuration in code

**Phase 4 Definition of Done — Per Module:**
- [ ] Unit tests written first (TDD) ✓
- [ ] All unit tests pass ✓
- [ ] Code coverage ≥ 80% ✓
- [ ] SOLID principles applied and verified in code review ✓
- [ ] No static analysis violations ✓
- [ ] CI pipeline green ✓
- [ ] Senior Software Engineer code review approved ✓

**Claude Prompt:**
```
Act as a Senior Software Engineer with TDD and clean code expertise.
Module: [NAME]
Interface contract: [FROM PHASE 3]

1. Write comprehensive unit tests first — cover happy path, edge cases, and all failure paths.
2. Implement the code to pass every test. Follow SOLID throughout.
3. Review your implementation against the interface contract. Does it fully comply?
4. What would a senior engineer reject in a code review of this implementation?
5. What refactoring is needed before this is production-grade?
```

---

### Phase 5 · INTEGRATE — Integration & System Testing
**Sprint Duration:** 1–2 sprints
**Lead Role:** Senior DevOps Engineer
**Supporting Roles:** Senior Software Engineer, Senior Platform Engineer
**V-Model Pair:** Integration Testing + System Testing — both run in this phase

**What must happen:**
- Connect all modules and verify that interface contracts hold under real conditions
- Senior DevOps executes automated integration test suite in a staging environment
- Senior Platform Engineer confirms staging is a true production-mirror
- System Testing validates the complete system against every requirement from Phase 1
- Performance testing: load tests, stress tests — verify NFR targets are met
- Security testing: penetration testing, dependency scanning, SAST/DAST results reviewed

**Senior DevOps Anti-Pattern Check:**
- Reject staging environments that differ from production in any material way
- Reject system tests that do not cover failure and recovery scenarios
- Reject deployments without passing security scan results
- Flag any performance result that does not meet the NFR targets from Phase 1

**Phase 5 Quality Gate — Cannot proceed without:**
- [ ] All integration tests pass ✓
- [ ] System tests pass against all Phase 1 requirements ✓
- [ ] Performance targets from NFRs met ✓
- [ ] Security scan clean — all critical and high findings resolved ✓
- [ ] Staging environment confirmed as production-mirror ✓
- [ ] Rollback procedure documented and tested ✓

**Claude Prompt:**
```
Act as a Senior DevOps Engineer and Senior Software Engineer.
Modules integrated: [LIST]
System requirements: [FROM PHASE 1]
NFR targets: [FROM PHASE 1]

1. What integration risks exist between these modules? Identify every boundary failure scenario.
2. What system test scenarios cover all requirements end-to-end?
3. Does the system meet its non-functional requirements? Where does it fall short?
4. What are the top 3 production failure modes — and how do we detect and recover?
5. Is there any gap between what was specified in Phase 1 and what was built? Be exact.
```

---

### Phase 6 · DELIVER — Acceptance Testing & Production Deployment
**Sprint Duration:** 1 sprint
**Lead Role:** Senior Solution Architect
**Supporting Roles:** All Roles
**V-Model Pair:** User Acceptance Testing — validates against every acceptance criterion from Phase 1

**What must happen:**
- UAT validates the system meets every acceptance criterion written in Phase 1
- Senior Solution Architect confirms architectural integrity is maintained in the final system
- Senior DevOps executes production deployment via the fully automated pipeline
- Senior Platform Engineer confirms production environment matches the defined topology
- Zero-downtime deployment strategy executed
- Post-deployment monitoring reviewed — no silent failures
- Full documentation and lessons log finalised

**Senior Architect Final Check:**
- Does the delivered system match the architecture that was designed?
- Has any architectural drift occurred during implementation? Document it.
- Are all ADRs still accurate — or do they need to be updated to reflect what was actually built?

**Phase 6 Quality Gate — Cannot deploy without:**
- [ ] All UAT acceptance criteria from Phase 1 pass ✓
- [ ] Senior Solution Architect architectural sign-off ✓
- [ ] Deployment pipeline executed successfully in staging ✓
- [ ] Rollback procedure tested and ready ✓
- [ ] Post-deployment monitoring active and alerting configured ✓
- [ ] Full documentation complete ✓
- [ ] Lessons log updated ✓

**Claude Prompt:**
```
Act as a Senior Solution Architect coordinating final delivery.
Acceptance criteria: [FROM PHASE 1]
What was built: [SUMMARY]

1. Verify the system against every acceptance criterion. Pass or fail — be explicit.
2. Has any architectural drift occurred? Document it precisely.
3. Are all ADRs still accurate? Update any that need revision.
4. What must be resolved before this is production-ready?
5. Produce the final documentation summary: what was built, how it works, and known limitations.
```

---

## IV. The Three Quality Gates

Every phase must pass all three before proceeding. No exceptions.

| Gate | Question | Who Enforces |
|------|----------|-------------|
| **Verified** | Are we building it correctly? (matches spec) | Senior Software Engineer |
| **Validated** | Are we building the right thing? (meets requirements) | Senior Solution Architect |
| **Production-Grade** | Would a senior engineer deploy this confidently? | All Roles |

---

## V. Clean Architecture Mandates

These rules are enforced by the Senior Solution Architect and Senior Software Engineer
at every phase. Violations are flagged immediately — not at delivery.

| Anti-Pattern | Why It Is Rejected | Correct Approach |
|---|---|---|
| **Spaghetti Architecture** | Untraceable dependencies, impossible to test or change | Clear bounded contexts, explicit interfaces |
| **God Objects / God Modules** | One module doing everything — untestable, unmaintainable | Single Responsibility — one reason to change |
| **Tight Coupling** | Change in one module breaks unrelated modules | Depend on abstractions, inject dependencies |
| **Shared Mutable State** | Race conditions, unpredictable behavior, untestable | Immutable data, explicit message passing |
| **Magic Numbers / Strings** | Undocumented, unmaintainable, unexplainable | Named constants with documented purpose |
| **Circular Dependencies** | Deadlock in reasoning and testing | One-directional dependency graphs |
| **Premature Optimisation** | Complexity without proven need | Measure first, optimise only where proven necessary |
| **TODO in Production Code** | Promises that are never fulfilled | File a formal backlog item or fix it immediately |
| **Untested Error Paths** | Failures discovered in production | Every failure path designed and tested explicitly |

---

## VI. Task Management Protocol

| # | Stage | Action | Owner | File |
|---|-------|--------|-------|------|
| 1 | **Plan** | Write full sprint plan before any code | All Roles | `tasks/todo.md` |
| 2 | **Verify** | Confirm plan meets architectural standards | Senior Solution Architect | — |
| 3 | **Track** | Update task status in real-time | All Roles | `tasks/todo.md` |
| 4 | **Explain** | Summarise all changes at sprint end | Lead Role for Phase | — |
| 5 | **Document** | Log results, decisions, and ADRs | All Roles | `tasks/todo.md` |
| 6 | **Evolve** | Update lessons after every correction | All Roles | `tasks/lessons.md` |

### Self-Correction Loop
- After any failure, correction, or deviation → update `tasks/lessons.md` immediately
- Write a specific rule to prevent recurrence — not a generic note
- Review all lessons at the **start of every sprint** — non-negotiable
- Mistake rate must trend toward zero across sprints

---

## VII. Sprint Template

Use at the start of every sprint across all phases.

```
── SPRINT START ─────────────────────────────────────────────────

CONTEXT
  Project:          [NAME]
  Phase:            [CURRENT PHASE]
  Sprint:           [N of N]
  Prior decisions:  [SUMMARY + ADR REFERENCES]
  Lessons reviewed: [KEY RULES FROM lessons.md]

SPRINT GOAL
  What we build:    [MODULE / FEATURE / INTEGRATION]
  V-Model pair:     [WHAT WE VERIFY OR VALIDATE THIS SPRINT]
  Acceptance:       [TESTABLE DONE CRITERIA]

TASKS
  [ ] Task 1   Owner: [ROLE]   Estimated: [HOURS]
  [ ] Task 2   Owner: [ROLE]   Estimated: [HOURS]
  [ ] Task 3   Owner: [ROLE]   Estimated: [HOURS]

── SPRINT END ───────────────────────────────────────────────────

REVIEW
  Passed:         [LIST]
  Failed:         [LIST]
  Root causes:    [EXACT ANALYSIS — NO VAGUE SUMMARIES]

QUALITY GATES
  Verified:         ✓ / ✗
  Validated:        ✓ / ✗
  Production-Grade: ✓ / ✗

ARCHITECTURAL DRIFT
  Any deviation from the agreed architecture: [YES / NO + DETAIL]
  ADRs updated: [YES / NO]

LESSONS EVOLVED
  New rule added to tasks/lessons.md: [SPECIFIC RULE]

── NEXT SPRINT READY ────────────────────────────────────────────
```

---

## VIII. Quick Reference

| Situation | Who to Invoke | Prompt Direction |
|-----------|--------------|-----------------|
| Starting a new project | Senior Solution Architect | Define requirements + architecture first |
| Architecture feels wrong | Senior Solution Architect | "Review this design. Where is it fragile, coupled, or unclear?" |
| Writing a module | Senior Software Engineer | TDD first — tests before implementation |
| Code smells in review | Senior Software Engineer | "Apply SOLID. What needs to change before this is mergeable?" |
| CI pipeline broken | Senior DevOps Engineer | "Point to the logs. Find root cause. Fix and prevent recurrence." |
| Environments inconsistent | Senior Platform Engineer | "Audit the environment diff. Enforce golden path." |
| Phase failing quality gate | All Roles | "What exactly is missing for this to pass? Be specific and exhaustive." |
| Architectural drift discovered | Senior Solution Architect | "Document the drift. Update the ADR. Decide: fix now or backlog with risk noted." |
| Final delivery check | Senior Solution Architect | "Verify every acceptance criterion. Flag any gap between spec and delivery." |

---

## IX. Glossary

| Term | Meaning |
|------|---------|
| **ADR** | Architecture Decision Record — documents a design decision, its context, and its rationale |
| **Agile** | Sprint-based iterative delivery with continuous feedback and backlog-driven prioritisation |
| **V-Model** | Each build phase is paired with a corresponding test phase — development and testing are parallel tracks |
| **Verification** | Confirming the product is built correctly — matches design and specification |
| **Validation** | Confirming the correct product is built — meets user and business requirements |
| **TDD** | Test-Driven Development — write tests before writing implementation |
| **SOLID** | Five clean code principles: Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion |
| **IaC** | Infrastructure as Code — all environments are version-controlled and reproducible |
| **Golden Path** | A pre-approved, standardised deployment and development template built by Platform Engineering |
| **GitOps** | The repository is the single source of truth for all environment configuration and deployment state |
| **Quality Gate** | A mandatory checkpoint every phase must pass before work continues |
| **Spaghetti Architecture** | Undisciplined, tightly coupled design with no clear boundaries — rejected on sight |
| **Definition of Done** | The explicit, non-negotiable criteria a task must meet to be considered complete |
| **Lessons Log** | A living document updated after every correction, reviewed at the start of every sprint |

---

*Version 4.0 · Agile + V-Model Hybrid · Senior Multi-Role Engineering Orchestration*
*Clean Architecture by Default · No Spaghetti · No Shortcuts · No Technical Debt Left Unaddressed*
*Built for use with Claude AI · Reusable across all future projects*
