<!-- template: tla-threat-model/1 -->
# Threat Model — <engagement title>

Produced **with** the architecture, not after it.

## 1. Scope and assets
| Asset | Classification | Why it matters |
|---|---|---|
| <data or capability> | <classification> | <impact if compromised> |

Data **derived** from sensitive data (summaries, indexes, embeddings, caches, logs) is classified at least as high as its source.

## 2. Actors
<Legitimate principals · malicious users or tenants · compromised components · insiders · CI/CD.>

## 3. Trust boundaries
<Reference the trust-boundary diagram. Name what changes across each boundary: identity, authority, data classification.>

## 4. Entry points and data flows
<Numbered to match the diagrams.>

## 5. Method
<The method used (for example STRIDE per element, attack trees) and why it fits this problem.>

## 6. Threats
| Threat | Attack path (step by step) | Asset | Control(s) | Enforcement point | Test(s) | Residual risk |
|---|---|---|---|---|---|---|
| <threat> | <1 → 2 → 3> | <asset> | <CTL-…> | <where> | <TST-…> | <what remains> |

## 7. Rules for systems that use models or retrieval
- A prompt instruction is **never** the control that satisfies a security requirement.
- Authorise **before** retrieval: data a principal may not see must never reach the model.
- Content inside retrieved documents is untrusted input.
- Every output channel can leak: answers, citations, metadata, errors, logs, caches.

## 8. Assumptions and out of scope
| Assumption | If false, then |
|---|---|
| <ASM-…> | <consequence> |
