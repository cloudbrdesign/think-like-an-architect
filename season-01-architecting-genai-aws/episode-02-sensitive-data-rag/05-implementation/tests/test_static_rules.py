"""L0 / L1 static rules: source code and template checks that fail the build if a control is weakened (no AWS)."""
import os
import re
import unittest

import support

APP = support.APP
TEMPLATE = os.path.join(support.IMPLEMENTATION, "infrastructure", "template.yaml")
SENSITIVITY = os.path.join(support.EPISODE, "06-validation", "sensitivity")

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def sources():
    for directory, _, files in os.walk(APP):
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(directory, name)
                yield os.path.relpath(path, APP), open(path, encoding="utf-8").read()


def load_template():
    class Loader(yaml.SafeLoader):
        pass

    def construct(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            value = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node, deep=True)
        else:
            value = loader.construct_mapping(node, deep=True)
        return {f"Fn::{suffix}" if suffix not in ("Ref", "Condition") else suffix: value}

    Loader.add_multi_constructor("!", construct)
    return yaml.load(open(TEMPLATE, encoding="utf-8"), Loader=Loader)


def statements(resource):
    for policy in resource["Properties"].get("Policies", []):
        for statement in policy["PolicyDocument"]["Statement"]:
            yield statement


def actions(statement):
    value = statement["Action"]
    return [value] if isinstance(value, str) else value


class SourceRules(unittest.TestCase):
    def test_no_negative_filter_operators_anywhere_in_the_application(self):
        for path, text in sources():
            code = re.sub(r'"""[\s\S]*?"""', "", text)
            code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())
            self.assertNotRegex(code, r"notEquals|notIn", path)

    def test_only_the_retrieval_gateway_calls_retrieve(self):
        callers = [path for path, text in sources() if re.search(r"(?<!retrieval_gateway)\.retrieve\(", text)]
        self.assertEqual(callers, [os.path.join("query", "retrieval_gateway.py")])
        combined = [path for path, text in sources() if "retrieve_and_generate" in text]
        self.assertEqual(combined, [])

    def test_no_cache_mechanisms(self):
        for path, text in sources():
            self.assertNotRegex(text, r"lru_cache|functools\.cache|cachePoint|CacheControl|cache_ttl", path)

    def test_no_module_level_state_in_authorization_and_verification_modules(self):
        for relative in ("query/policy_decision.py", "core/verification.py", "core/constraints.py",
                         "adapters/stores.py", "query/retrieval_gateway.py"):
            text = open(os.path.join(APP, relative), encoding="utf-8").read()
            module_level = [line for line in text.splitlines()
                            if re.match(r"^[a-z_][a-z0-9_]*\s*=\s*(\{|\[|dict\(|list\(|set\()", line)]
            self.assertEqual(module_level, [], relative)

    def test_handler_caches_only_sdk_clients(self):
        text = open(os.path.join(APP, "query", "handler.py"), encoding="utf-8").read()
        self.assertEqual(re.findall(r"^(_[a-z_]+)\s*=\s*\{\}", text, re.MULTILINE), ["_clients"])

    def test_normal_source_contains_no_variant_code(self):
        for path, text in sources():
            self.assertNotIn("SENSITIVITY VARIANT", text, path)
            self.assertNotIn("FAULT:", text, path)

    def test_every_variant_is_marked(self):
        for name in ("eligibility_removed.py", "labels_corrupted.py", "claims_as_grants.py"):
            self.assertIn("SENSITIVITY VARIANT — TEST ONLY", open(os.path.join(SENSITIVITY, name)).read())

    def test_model_logging_and_prompt_content_are_never_logged(self):
        for path, text in sources():
            for match in re.finditer(r"print\((.*)\)", text):
                self.assertRegex(match.group(1), r"json\.dumps\(\{k: fields\[k\]", path)


@unittest.skipIf(yaml is None, "PyYAML not installed (pip install pyyaml) — template rules not checked")
class TemplateRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = load_template()
        cls.resources = cls.template["Resources"]

    def roles(self):
        return {name: r for name, r in self.resources.items() if r["Type"] == "AWS::IAM::Role"}

    def holders(self, action):
        return sorted(name for name, role in self.roles().items()
                      if any(action in actions(s) for s in statements(role) if s["Effect"] == "Allow"))

    def test_only_the_query_role_can_retrieve_from_either_tier(self):
        self.assertEqual(self.holders("bedrock:Retrieve"), ["QueryRole"])

    def test_only_the_ingestion_role_can_ingest(self):
        self.assertEqual(self.holders("bedrock:IngestKnowledgeBaseDocuments"), ["IngestionRole"])

    def test_each_knowledge_base_role_reads_only_its_own_tier(self):
        for tier in ("Shared", "Restricted"):
            role = self.resources[f"{tier}KnowledgeBaseRole"]
            text = repr(list(statements(role)))
            other = "Restricted" if tier == "Shared" else "Shared"
            self.assertNotIn(f"{other}VectorIndex", text)
            self.assertNotIn(f"-{other.lower()}-sections-", text)

    def test_section_bucket_policies_restrict_reads_and_writes(self):
        for tier in ("Shared", "Restricted"):
            policy = repr(self.resources[f"{tier}SectionBucketPolicy"]["Properties"]["PolicyDocument"])
            self.assertIn(f"{tier}KnowledgeBaseRole", policy)
            self.assertIn("IngestionRole", policy)

    def test_no_wildcard_actions_or_resources_in_application_roles(self):
        for name, role in self.roles().items():
            for statement in statements(role):
                self.assertNotIn("*", actions(statement), name)
                self.assertNotEqual(statement.get("Resource"), "*", name)

    def test_log_retention_one_day_and_no_api_cache(self):
        for name, resource in self.resources.items():
            if resource["Type"] == "AWS::Logs::LogGroup":
                self.assertEqual(resource["Properties"]["RetentionInDays"], 1, name)
        self.assertNotRegex(open(TEMPLATE).read(), r"(?i)cachingenabled|cachecluster|CacheTtl")

    def test_access_log_format_has_no_body(self):
        stage = [r for r in self.resources.values() if r["Type"] == "AWS::ApiGatewayV2::Stage"][0]
        self.assertNotRegex(stage["Properties"]["AccessLogSettings"]["Format"], r"(?i)body|requestBody")

    def test_query_function_invocable_only_through_the_api(self):
        policy = repr(self.resources["QueryInvokeOnlyThroughApi"]["Properties"]["PolicyDocument"])
        self.assertIn("DenyEveryOtherCaller", policy)

    def test_generation_model_is_in_region(self):
        parameter = self.template["Parameters"]["GenerationModelId"]
        self.assertFalse(re.match(r"^(us|eu|apac|global)\.", parameter["Default"]))
        self.assertIn("AllowedPattern", parameter)


if __name__ == "__main__":
    unittest.main()
