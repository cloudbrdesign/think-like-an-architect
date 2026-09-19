"""The deployment under test: account guard, stack outputs and SDK clients (operator credentials — PRIVILEGED)."""
import json
import os

from harness.common import tla_ops


def _sha256_from_code_key(key):
    """'functions/<sha256>/query.zip' → the sha256 actually deployed, read from the stack's own parameters."""
    parts = (key or "").split("/")
    return parts[1] if len(parts) == 3 and len(parts[1]) == 64 else None


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
        # Immutable identity. A stack NAME is reused across deployments and proves nothing about which deployment
        # produced a result — the canonical normal stack was destroyed and rebuilt under the same name, and the
        # earlier evidence cannot now be attributed to either one. Every run records what cannot be reused.
        self.stack_id = stack["StackId"]
        self.stack_created = stack.get("CreationTime")
        parameters = {p["ParameterKey"]: p.get("ParameterValue") for p in stack.get("Parameters", [])}
        self.package_sha256 = {name: _sha256_from_code_key(parameters.get(f"{name.title()}CodeKey"))
                               for name in ("query", "change")}
        # Read from the stack's own parameters — never from the variant name, the local config, or the mapping's
        # current State. A variant whose premise is "delivery was never active" has to prove that from the deployment
        # it actually ran against, and an absent parameter stays None rather than being assumed.
        self.change_notifications_enabled = parameters.get("ChangeNotificationsEnabled")
        self.replaced_modules = self._replaced_modules()

    def _replaced_modules(self):
        """The local build's replaced modules, claimed ONLY when its packages are the ones actually deployed.

        The build directory is local and mutable; the stack's parameters are not. If they disagree, the honest answer
        is that this harness cannot say what was replaced — never the local manifest's guess.
        """
        path = os.path.join(tla_ops.BUILD, self.variant, "manifest.json")
        try:
            with open(path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            return None
        built = {name: (manifest.get("packages", {}).get(name) or {}).get("sha256") for name in ("query", "change")}
        if manifest.get("variant") != self.variant or built != self.package_sha256:
            return None
        return manifest.get("replaced_modules")

    def identity(self):
        """What distinguishes this deployment from another wearing the same stack name."""
        return {"stack_name": self.stack_name, "stack_id": self.stack_id,
                "stack_created": self.stack_created, "region": self.region, "variant": self.variant,
                "package_sha256": self.package_sha256, "replaced_modules": self.replaced_modules,
                "change_notifications_enabled": self.change_notifications_enabled}

    def client(self, name, **config):
        key = (name, repr(sorted(config.items())))
        if key not in self._clients:
            from botocore.config import Config
            self._clients[key] = self.session.client(name, config=Config(**config) if config else None)
        return self._clients[key]

    def knowledge_base(self, tier):
        prefix = "Shared" if tier == "shared" else "Restricted"
        return self.outputs[f"{prefix}KnowledgeBaseId"], self.outputs[f"{prefix}DataSourceId"]
