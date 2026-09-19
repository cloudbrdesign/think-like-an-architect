# Episode 03 — what we observed

These are the observations behind the lesson, from the educational implementation running on AWS with synthetic data,
in September 2026. They show what happened under the tested conditions. They are not a certification, a compliance
statement, or a claim that any system is secure.

## 1 · Present is not current

We created a deployment with change notifications **turned off from the moment it was created**, so the index would
never be told about a change.

- A question about a depot safety induction was **answered** from its document.
- We **withdrew** that document in the records system, without changing its version.
- The document's copies were **still in the index**, and the same question **retrieved them**.
- The copies still **matched** the records system on document, label, scope and version.
- The assistant **refused** to use them, because on that request it asked the records system, and the records system
  said the document was no longer in force. Nothing was generated and nothing was cited.

**What it shows:** content being present is not the same as content being current. Safety came from checking authority
on the request, not from the index being up to date.

## 2 · Reconciliation earns completeness

In that same deployment, with no notifications at all:

- **Reconciliation** compared every document in the records system with the index, named the withdrawn document as
  **diverged**, removed its copies, and a second pass found nothing left to repair.
- In separate runs, it found a document the index had **never received** and built it, and it found a copy with **no
  record behind it** and removed it.

**What it shows:** a change that was never delivered is invisible to delivery. Only a comparison against authority can
show that nothing is missing — and it can also repair what it finds.

## 3 · Failure is visible, retried and escalated

On the normal deployment, with notifications on, we made one document's source unreadable and then changed its
classification upwards.

- The change could not be applied, so it **stayed pending** instead of disappearing.
- It was **retried** through the real application path — its attempt count rose from one to two.
- It **kept its original clock**, so the age of the incident stayed honest.
- Its window for that kind of change is zero seconds. When the window passed, it raised an **alert naming the kind of
  change and the document**, and a **monitoring alarm** changed state.
- Once the source was restored, the change was applied and the **incident cleared**.

**What it shows:** a change that cannot be applied must stay visible, be retried, and be escalated — never silently
lost.

## The principle

**Events accelerate convergence. Authority determines truth. Reconciliation restores consistency.**
