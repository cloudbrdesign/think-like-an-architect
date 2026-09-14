"""Shared modules of the Veltamere Document Assistant (Episode 01 learner implementation).

Read these four files to see the whole isolation argument:
  tenant_context.py          tenant authority comes only from verified claims and the registry
  retrieval_scope.py         THE PRIMARY CONTROL: the only place the tenant constraint is built
  ownership_verification.py  defence in depth: retrieved results are checked before generation
  ../../infrastructure/template.yaml  who is allowed to do what
"""
