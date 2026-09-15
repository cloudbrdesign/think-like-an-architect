"""Synthetic persona identities (identity-provider stand-in, TS-E02-04). PRIVILEGED: sandbox administrator credentials.

Passwords are random per harness process, held only in memory, never written or printed. Tokens are never printed or
stored in evidence; `claims()` decodes a token payload for display without verifying it (verification is the edge's job).
"""
import base64
import json
import secrets
import time

TOKEN_REUSE_SECONDS = 240          # access tokens live 5 minutes


class Identities:
    def __init__(self, target):
        self.idp = target.client("cognito-idp")
        self.pool = target.outputs["UserPoolId"]
        self.clients = {"app": target.outputs["AppClientId"], "other": target.outputs["OtherAppClientId"]}
        self._passwords, self._tokens = {}, {}

    @staticmethod
    def group_names(persona):
        if not persona.get("mirror_to_token_groups"):
            return []
        return [f"domain.{d}" for d in persona["domains"]] + [f"case.{c}" for c in persona["cases"]]

    def ensure_group(self, group):
        try:
            self.idp.create_group(UserPoolId=self.pool, GroupName=group)
        except self.idp.exceptions.GroupExistsException:
            pass

    def ensure_user(self, username, groups):
        try:
            self.idp.admin_create_user(UserPoolId=self.pool, Username=username, MessageAction="SUPPRESS",
                                       TemporaryPassword=self._new_password())
        except self.idp.exceptions.UsernameExistsException:
            pass
        self.set_groups(username, groups)
        return self.subject(username)

    def set_groups(self, username, groups):
        current = {g["GroupName"] for g in self.idp.admin_list_groups_for_user(UserPoolId=self.pool, Username=username,
                                                                               Limit=60)["Groups"]}
        for group in sorted(set(groups) - current):
            self.ensure_group(group)
            self.idp.admin_add_user_to_group(UserPoolId=self.pool, Username=username, GroupName=group)
        for group in sorted(current - set(groups)):
            self.idp.admin_remove_user_from_group(UserPoolId=self.pool, Username=username, GroupName=group)

    def subject(self, username):
        attributes = self.idp.admin_get_user(UserPoolId=self.pool, Username=username)["UserAttributes"]
        return next(a["Value"] for a in attributes if a["Name"] == "sub")

    @staticmethod
    def _new_password():
        return "Aa1!-" + secrets.token_urlsafe(24)

    def token(self, username, client="app", fresh=False):
        key = (username, client)
        cached = self._tokens.get(key)
        if cached and not fresh and time.time() - cached["issued_at"] < TOKEN_REUSE_SECONDS:
            return cached["access"]
        if username not in self._passwords:
            password = self._new_password()
            self.idp.admin_set_user_password(UserPoolId=self.pool, Username=username, Password=password, Permanent=True)
            self._passwords[username] = password
        auth = self.idp.admin_initiate_auth(UserPoolId=self.pool, ClientId=self.clients[client],
                                            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                                            AuthParameters={"USERNAME": username,
                                                            "PASSWORD": self._passwords[username]})["AuthenticationResult"]
        self._tokens[key] = {"access": auth["AccessToken"], "issued_at": time.time()}
        return auth["AccessToken"]

    def issued_at(self, username, client="app"):
        return self._tokens[(username, client)]["issued_at"]

    @staticmethod
    def claims(token):
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
