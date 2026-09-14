"""Permission exclusivity (TST-SEC-023; CTL-008, CTL-009, CTL-010, CTL-013). OP-5: policy simulation of every stack role.

Expected: retrieve — gateway only; index/remove — ingestion only; vectors — indexing pipeline only; originals — ingestion
and indexing only; registry tenant writes — nobody in the application; functions — the API only.
The learner's sandbox administrator remains a privileged path by design (RR-02) and is reported, not hidden.
"""

SUITE = "permissions"


def _simulate(iam, role_arn, action, resource, context=None):
    kwargs = {"PolicySourceArn": role_arn, "ActionNames": [action], "ResourceArns": [resource]}
    if context:
        kwargs["ContextEntries"] = context
    return iam.simulate_principal_policy(**kwargs)["EvaluationResults"][0]["EvalDecision"]


def run(ctx):
    t, out = ctx.target, ctx.target.outputs
    iam, cfn, lam, s3 = t.client("iam"), t.client("cloudformation"), t.client("lambda"), t.client("s3")
    roles = {"QueryRole": out["QueryRoleArn"], "IngestionRole": out["IngestionRoleArn"],
             "KnowledgeBaseServiceRole": out["KnowledgeBaseServiceRoleArn"]}
    kb, index, bucket = out["KnowledgeBaseArn"], out["VectorIndexArn"], out["DocumentBucket"]
    region, account = t.region, t.account
    registry = f"arn:aws:dynamodb:{region}:{account}:table/{out['RegistryTable']}"
    leading = lambda key: [{"ContextKeyName": "dynamodb:LeadingKeys", "ContextKeyValues": [key], "ContextKeyType": "stringList"}]
    checks = [
        ("retrieve", "bedrock:Retrieve", kb, None, {"QueryRole"}),
        ("index documents", "bedrock:IngestKnowledgeBaseDocuments", kb, None, {"IngestionRole"}),
        ("remove documents", "bedrock:DeleteKnowledgeBaseDocuments", kb, None, {"IngestionRole"}),
        ("query vectors directly", "s3vectors:QueryVectors", index, None, {"KnowledgeBaseServiceRole"}),
        ("read originals", "s3:GetObject", f"arn:aws:s3:::{bucket}/tenants/tenant-a/documents/x/source.md", None,
         {"IngestionRole", "KnowledgeBaseServiceRole"}),
        ("write originals", "s3:PutObject", f"arn:aws:s3:::{bucket}/tenants/tenant-a/documents/x/source.md", None, {"IngestionRole"}),
        ("write tenant registry entries", "dynamodb:PutItem", registry, leading("TENANT#tenant-a"), set()),
        ("write ownership records", "dynamodb:PutItem", registry, leading("DOC#x"), {"IngestionRole"}),
        ("invoke query service (identity policy)", "lambda:InvokeFunction",
         f"arn:aws:lambda:{region}:{account}:function:{out['QueryFunctionName']}", None, set()),
        ("invoke ingestion service (identity policy)", "lambda:InvokeFunction",
         f"arn:aws:lambda:{region}:{account}:function:{out['IngestionFunctionName']}", None, set()),
        ("generate with the In-Region model", "bedrock:InvokeModel",
         f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-micro-v1:0", None, {"QueryRole"}),
        ("deployment compatibility action apigateway:TagResource (FC-04)", "apigateway:TagResource",
         f"arn:aws:apigateway:{region}::/apis/x/stages", None, set()),
    ]
    matrix, violations = [], []
    for label, action, resource, context, allowed in checks:
        row = {"capability": label, "action": action, "decisions": {}}
        for name, arn in roles.items():
            decision = _simulate(iam, arn, action, resource, context)
            row["decisions"][name] = decision
            if (decision == "allowed") != (name in allowed):
                violations.append(f"{name} {'may' if decision == 'allowed' else 'may not'} {label}")
        matrix.append(row)
    resources = cfn.describe_stack_resources(StackName=t.stack_name)["StackResources"]
    stack_roles = sorted(r["LogicalResourceId"] for r in resources if r["ResourceType"] == "AWS::IAM::Role")
    identity_pools = [r["LogicalResourceId"] for r in resources if r["ResourceType"] == "AWS::Cognito::IdentityPool"]
    if stack_roles != sorted(roles):
        violations.append(f"unexpected principals in the stack: {stack_roles}")
    if identity_pools:
        violations.append("an identity pool would give end users AWS credentials")
    resource_policies = {}
    for function in (out["QueryFunctionName"], out["IngestionFunctionName"]):
        import json
        statements = json.loads(lam.get_policy(FunctionName=function)["Policy"])["Statement"]
        resource_policies[function] = sorted((s.get("Sid"), s["Effect"]) for s in statements)
        if ("DenyEveryOtherCaller", "Deny") not in resource_policies[function]:
            violations.append(f"{function} lacks the explicit Deny for non-API callers")
    bucket_policy = [s["Sid"] for s in __import__("json").loads(s3.get_bucket_policy(Bucket=bucket)["Policy"])["Statement"]]
    for sid in ("DenyInsecureTransport", "DenyDocumentWritesExceptIngestionService", "DenyDocumentReadsExceptIngestionServiceAndIndexing"):
        if sid not in bucket_policy:
            violations.append(f"bucket policy lacks {sid}")
    ctx.run.record(
        "TST-SEC-023", SUITE, ["SEC-009", "SEC-010", "SEC-007"], ["CTL-008", "CTL-009", "CTL-010", "CTL-013"], "L1",
        "EXCLUSIVE: only the gateway retrieves, only ingestion indexes, only indexing touches vectors, only the API invokes",
        "FAIL" if violations else "PASS",
        "; ".join(violations) if violations else "every capability held only by its intended principal; no application role holds the FC-04 deployment action",
        {"simulation_matrix": matrix, "stack_roles": stack_roles, "identity_pools": identity_pools,
         "function_resource_policies": resource_policies, "document_bucket_policy_statements": bucket_policy,
         "privileged_path": "the sandbox administrator/deployment identity can change these policies (RR-02, CH-01, CH-02)"},
        privileged=True)
