"""The deployment under test: account guard, stack outputs and SDK clients (operator credentials — PRIVILEGED)."""
from harness.common import tla_ops


class Target:
    def __init__(self, variant="normal"):
        if variant not in tla_ops.VARIANTS:
            raise ValueError(f"unknown variant {variant}")
        self.variant = variant
        self.config = tla_ops.load_config()
        self.session = tla_ops.session(self.config)
        self.account = tla_ops.account_guard(self.config, self.session, quiet=True)
        self.region = self.session.region_name
        self.names = tla_ops.names(variant, self.account)
        self.stack_name = self.names["stack"]
        self._clients = {}
        stack = self.client("cloudformation").describe_stacks(StackName=self.stack_name)["Stacks"][0]
        if stack["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            raise RuntimeError(f"{self.stack_name} is {stack['StackStatus']}")
        self.outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        if self.outputs.get("Variant") != variant:
            raise RuntimeError(f"{self.stack_name} reports variant {self.outputs.get('Variant')}, expected {variant}")

    def client(self, name, **config):
        key = (name, repr(sorted(config.items())))
        if key not in self._clients:
            from botocore.config import Config
            self._clients[key] = self.session.client(name, config=Config(**config) if config else None)
        return self._clients[key]

    def knowledge_base(self, tier):
        prefix = "Shared" if tier == "shared" else "Restricted"
        return self.outputs[f"{prefix}KnowledgeBaseId"], self.outputs[f"{prefix}DataSourceId"]
