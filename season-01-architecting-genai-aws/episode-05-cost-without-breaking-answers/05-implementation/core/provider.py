#!/usr/bin/env python3
"""PUBLISHABLE CORE — local answer generator.

DELIBERATELY NOT A MODEL CLIENT. The lab teaches an ACCOUNTING question — what work is removed and
what preservation work remains — and that question does not need a model to answer. Running locally
means the lab needs no AWS account, no credentials, no network and no spend, and creates nothing to
clean up.

Episode 05's own evidence is the reason this matters: real model output at temperature 0 was NOT
deterministic, so a lab built on live inference would give every learner different numbers for
reasons that have nothing to do with the architecture being taught.
"""


class LocalProvider:
    name = "local-deterministic"

    def generate(self, question, sections):
        steps = [s for sec in sections for s in sec.steps]
        text = " ".join(f"{i + 1}. {s}." for i, s in enumerate(steps))
        return {"text": text, "model_id": self.name,
                "input_tokens": sum(len(sec.text.split()) for sec in sections) + len(question.split()),
                "output_tokens": len(text.split())}
