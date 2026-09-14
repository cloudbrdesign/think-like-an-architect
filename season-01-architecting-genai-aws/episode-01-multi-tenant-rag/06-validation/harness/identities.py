"""Test identities (identity-provider stand-in, TS-11). PRIVILEGED: uses administrator credentials in the sandbox.

Passwords are random per harness process, held only in memory, and never written or printed. Tokens are never printed
or stored; `claims()` decodes a token's payload for display without verifying it (verification is the API edge's job).
"""
import base64
import json
import secrets
import time

TOKEN_REUSE_SECONDS = 240  # access tokens live 5 minutes


class Identities:
    def __init__(self, target):
        self.target = target
        self.idp = target.client("cognito-idp")
        self.pool = target.outputs["UserPoolId"]
        self.clients = {"app": target.outputs["AppClientId"], "other": target.outputs["OtherAppClientId"]}
        self._passwords, self._tokens = {}, {}

    def ensure_group(self, group):
        try:
            self.idp.create_group(UserPoolId=self.pool, GroupName=group)
        except self.idp.exceptions.GroupExistsException:
            pass

    def ensure_user(self, user, groups):
        try:
            self.idp.admin_create_user(UserPoolId=self.pool, Username=user, MessageAction="SUPPRESS",
                                       TemporaryPassword=self._new_password())
        except self.idp.exceptions.UsernameExistsException:
            pass
        current = {g["GroupName"] for g in self.idp.admin_list_groups_for_user(UserPoolId=self.pool, Username=user)["Groups"]}
        for group in set(groups) - current:
            self.ensure_group(group)
            self.idp.admin_add_user_to_group(UserPoolId=self.pool, Username=user, GroupName=group)
        for group in current - set(groups):
            self.idp.admin_remove_user_from_group(UserPoolId=self.pool, Username=user, GroupName=group)
        self._tokens = {k: v for k, v in self._tokens.items() if k[0] != user}

    @staticmethod
    def _new_password():
        return "Aa1!-" + secrets.token_urlsafe(24)

    def tokens(self, user, client="app", fresh=False):
        key = (user, client)
        cached = self._tokens.get(key)
        if cached and not fresh and time.time() - cached["issued_at"] < TOKEN_REUSE_SECONDS:
            return cached
        if user not in self._passwords:
            password = self._new_password()
            self.idp.admin_set_user_password(UserPoolId=self.pool, Username=user, Password=password, Permanent=True)
            self._passwords[user] = password
        result = self.idp.admin_initiate_auth(UserPoolId=self.pool, ClientId=self.clients[client],
                                              AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                                              AuthParameters={"USERNAME": user, "PASSWORD": self._passwords[user]})
        auth = result["AuthenticationResult"]
        self._tokens[key] = {"access": auth["AccessToken"], "id": auth["IdToken"], "issued_at": time.time()}
        return self._tokens[key]

    def access(self, user, client="app"):
        return self.tokens(user, client)["access"]

    @staticmethod
    def claims(token):
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
