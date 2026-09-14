"""Target discovery and the wrong-target guard.

Before any suite runs, the harness checks:
  - the account matches TLA_EXPECTED_ACCOUNT when it is set, and shows the account and region;
  - the stack exists, is complete, and carries the episode tags;
  - the stack's Variant tag and output match the variant the command asked for (normal suites never run against the
    sensitivity stack, and the sensitivity suite never runs against the normal stack);
  - each deployed function's code hash equals the locally built package for that variant.
Any mismatch raises GuardRefused before the API is called.
"""
import json
import os

from harness.common import IMPLEMENTATION, GuardRefused, tla_ops

EPISODE_TAGS = {"Project": "CloudBreweryLabs", "Course": "ThinkLikeAnArchitect", "Season": "01", "Episode": "01"}


class Target:
    def __init__(self, variant, stack_override=None, check_code=True, require_stack=True):
        self.config = tla_ops.load_config()
        self.session = tla_ops.session(self.config)
        self.region = self.session.region_name
        identity = self.session.client("sts").get_caller_identity()
        self.account = identity["Account"]
        self.caller = identity["Arn"]
        expected = self.config.get("TLA_EXPECTED_ACCOUNT")
        if expected and expected != self.account:
            raise GuardRefused(f"account {self.account} is not TLA_EXPECTED_ACCOUNT {expected}")
        self.variant = variant
        self.names = tla_ops.names(variant, self.account)
        self.stack_name = stack_override or self.names["stack"]
        self._clients = {}
        self.outputs, self.manifest = {}, {}
        if require_stack:
            self._check_stack(check_code)

    def client(self, name):
        if name not in self._clients:
            self._clients[name] = self.session.client(name)
        return self._clients[name]

    def _check_stack(self, check_code):
        try:
            stack = self.client("cloudformation").describe_stacks(StackName=self.stack_name)["Stacks"][0]
        except Exception as error:  # noqa: BLE001
            raise GuardRefused(f"stack {self.stack_name} not found ({type(error).__name__})") from error
        if stack["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            raise GuardRefused(f"stack {self.stack_name} is {stack['StackStatus']}")
        tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
        for key, value in EPISODE_TAGS.items():
            if tags.get(key) != value:
                raise GuardRefused(f"stack {self.stack_name} tag {key}={tags.get(key)!r}, expected {value!r}")
        self.outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        if tags.get("Variant") != self.variant or self.outputs.get("Variant") != self.variant:
            raise GuardRefused(f"stack {self.stack_name} is variant {tags.get('Variant')!r}; this command targets "
                               f"{self.variant!r}")
        if check_code:
            manifest_path = os.path.join(IMPLEMENTATION, "build", self.variant, "manifest.json")
            if not os.path.exists(manifest_path):
                raise GuardRefused(f"no local build for {self.variant}: run scripts/build.sh {self.variant}")
            self.manifest = json.load(open(manifest_path))
            lam = self.client("lambda")
            for function, output in (("query", "QueryFunctionName"), ("ingestion", "IngestionFunctionName")):
                deployed = lam.get_function_configuration(FunctionName=self.outputs[output])["CodeSha256"]
                if deployed != self.manifest["packages"][function]["lambda_code_sha256"]:
                    raise GuardRefused(f"deployed {function} code does not match build/{self.variant}/{function}.zip")

    def describe(self):
        return {"stack": self.stack_name, "variant": self.variant, "region": self.region, "account": self.account}
