---
name: legacy-modernization-domain
description: Enforces enterprise legacy-modernization standards — strangler fig migration (never big-bang rewrites), bounded-context-based microservice extraction, stateless REST APIs with generated OpenAPI specs, and cost-aware, secret-safe cloud infrastructure. Use this whenever analyzing a monolith for refactoring, planning or generating a microservices migration, extracting a service from an existing codebase, writing or reviewing Terraform/IaC for a modernization effort, or reviewing infrastructure code for hardcoded secrets or deprecated modules — even if the user just says "help me break this app apart" or "review our infra" without naming strangler fig, bounded contexts, or Terraform explicitly.
---

# Legacy Modernization Domain

Modernization projects fail less often from bad code than from bad sequencing and bad boundaries: a rewrite attempted all at once with no rollback path, or services split along the wrong lines so they end up more tangled than the monolith they replaced. This skill encodes the domain judgment that keeps that from happening — it's the business logic layer that sits above raw code generation, deciding _what_ should be extracted, _how_, and _in what order_, before any refactoring code gets written.

## 1. Strangler fig is the default migration pattern — never propose a big-bang rewrite

Explain to the user, if it isn't already agreed: the strangler fig pattern routes traffic for a given capability through a facade, incrementally moves that capability's logic into a new service behind the facade, and only retires the corresponding legacy code once the new path is verified in production. The monolith and the new services run side by side for the duration of the migration, not as a "before/after" cutover.

When asked to "modernize" or "refactor" a monolith, don't generate a full-system rewrite. Instead:

1. Identify the routing/facade layer (API gateway, reverse proxy, or a thin layer inside the monolith itself) that will direct traffic to either the legacy path or the new service, per capability.
2. Pick the first capability to extract using the prioritization order in §2 — not the easiest one to code, the one that provides the best proof-of-migration-path with the least risk.
3. Generate the new service so it can run alongside the legacy code with a feature flag or routing rule deciding which path serves a given request, not as a replacement that assumes the legacy path is already gone.
4. Never generate code that deletes or bypasses legacy functionality as part of the same change that adds the new service. Retirement of legacy code is a separate, later step, gated on verification.

If a user explicitly asks for a big-bang rewrite, don't silently comply — name the risk (no incremental rollback, all-or-nothing cutover) and confirm that's actually what they want before generating it.

## 2. Extract services along bounded contexts, not along file/module boundaries

A bounded context is a boundary within which a domain term has one consistent meaning and one team/service owns its data. Splitting services along technical layers (e.g., "the database layer becomes a service," "the validation logic becomes a service") instead of domain boundaries is the single most common cause of "microservices" that are really just a distributed monolith with network calls added.

Before extracting anything, identify bounded contexts using this checklist, in order:

1. **List the domain nouns** the monolith operates on (e.g., Order, Customer, Inventory, Invoice) and group the operations (verbs) that act on each.
2. **Find where the same noun means different things to different parts of the system.** ("Customer" in the billing module needs payment terms; "Customer" in the shipping module needs an address and delivery preferences — these are two bounded contexts, not one shared "Customer service," even though they'd naively look like the same entity.)
3. **Trace data ownership.** Whichever context creates and is the source of truth for a piece of data owns it; other contexts consume a copy or reference, they don't share a live table across service boundaries.
4. **Check transaction boundaries.** If two operations must succeed or fail together as one ACID transaction today, that's a strong signal they belong in the same bounded context (at least initially) — splitting them apart forces distributed transaction handling (sagas, compensating actions) that should be a deliberate later decision, not an accidental byproduct of where you happened to draw the first line.
5. **Prioritize extraction order by: highest business volatility (changes often) + lowest coupling to the rest of the monolith first.** High-change, low-coupling contexts get the most benefit from independent deployability and are the safest place to prove the migration pattern works.

## 3. Every extracted service is a stateless REST API with a generated OpenAPI spec

- **Stateless**: no session state, in-memory caches of request-scoped data, or sticky-session assumptions held in the service process between requests. Any state that must persist belongs in the service's own datastore (owned per §2), not in application memory.
- **REST, resource-oriented**: endpoints model the bounded context's domain resources and their operations (`POST /orders`, `GET /orders/{id}`), not RPC-style action names (`POST /doOrderThing`) carried over from the monolith's internal method calls.
- **OpenAPI spec is generated, not hand-maintained separately from the code.** Use the framework's native generation (FastAPI's automatic OpenAPI, springdoc for Spring Boot, etc.) so the spec can never drift out of sync with the actual implementation. If the target framework has no native generation, generate the spec from the same source-of-truth models/schemas the code uses, and flag this as a gap if no such mechanism exists.
- **Version the API explicitly** (URL path or header versioning) from the first extracted service — a migration that will run for months needs to be able to evolve one service's contract without breaking the facade routing to it.

## 4. Cloud infrastructure: cost-aware containerization, and hard flags on secrets and deprecated modules

When generating or reviewing Terraform/IaC for a modernization effort:

- **Containerize for the workload's actual profile**, not the largest available instance by default. Size requests/limits from observed or estimated resource use; prefer smaller, horizontally-scaled containers over a few oversized ones unless the workload has a specific reason (large in-memory state, GPU need) to run large. Default to spot/preemptible or scale-to-zero options for non-critical or batch workloads where the target platform supports them.
- **Hardcoded secrets are a hard stop, not a style note.** Flag any of the following immediately and refuse to leave them unaddressed in generated code: literal API keys, passwords, connection strings, or tokens in `.tf`, `.tfvars`, Dockerfiles, or application config committed to source. Replace with a reference to the platform's secret manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, or the equivalent) and note the substitution explicitly to the user rather than silently swapping it in.
- **Deprecated or unmaintained Terraform modules get flagged before use, not discovered later.** Before generating infrastructure code that depends on a third-party module, check whether it's marked deprecated/archived by its maintainer or pinned to a provider version with known EOL, and say so — propose the maintained replacement or the first-party resource equivalent instead of silently using the old module because it matches an existing pattern in the codebase.

## Review checklist (in priority order)

When reviewing an existing modernization effort or generated code, check in this order — each earlier failure tends to make the later ones worse:

1. Is this a big-bang cutover instead of a strangler fig increment? (§1)
2. Are service boundaries drawn along domain bounded contexts, or along technical layers / file structure? (§2)
3. Does each service hold request-scoped state statelessly, and is its OpenAPI spec generated from its actual code? (§3)
4. Are there hardcoded secrets anywhere in the IaC or app config? (§4)
5. Is any Terraform module deprecated, archived, or pinned to an EOL provider version? (§4)
6. Is the container/infra sizing proportionate to the actual workload, or defaulted to something oversized?

## Reference

`references/patterns.md` has concrete examples: a strangler fig facade/routing snippet, a bounded-context worksheet example (splitting a monolithic "Order" module into two services), a minimal FastAPI service with generated OpenAPI, and Terraform before/after examples for hardcoded secrets and a deprecated module replacement.
