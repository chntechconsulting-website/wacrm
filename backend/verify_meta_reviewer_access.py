"""Verify the production META_REVIEWER account against the live API.

Run from the repository root or the backend directory:

    backend\\venv\\Scripts\\python.exe backend\\verify_meta_reviewer_access.py

The password is prompted for with getpass and is never written to disk, logged,
or included in request output. No WhatsApp message is sent.

The script checks:
- login and /auth/me role;
- the two allowed screens' API endpoints;
- that leads, customers, users, roles, reports, notifications, IVR, settings and
  follow-ups are blocked with 403;
- that onboarding/sync actions are blocked with 403.
"""

import argparse
import getpass
import json
import sys

import httpx

DEFAULT_BASE_URL = "https://www.wapluscrm.in/api"
DEFAULT_USERNAME = "metareview"

ALLOWED_GET = [
    "/auth/me",
    "/whatsapp/config-status",
    "/whatsapp/conversations",
    "/whatsapp/coexistence/status",
    "/whatsapp/coexistence/events?limit=5",
    "/whatsapp/coexistence/templates",
]

DENIED_GET = [
    "/leads",
    "/leads/stats",
    "/customers",
    "/users",
    "/roles",
    "/reports",
    "/notifications",
    "/ivr/calls",
    "/settings",
    "/followups",
    "/dashboard",
]

DENIED_POST = [
    ("/whatsapp/coexistence/exchange", {}),
    ("/whatsapp/coexistence/refresh", {}),
    ("/whatsapp/coexistence/sync", {"resource": "contacts"}),
    ("/whatsapp/coexistence/session-log", {}),
]


class Checker:
    def __init__(self, base_url, session):
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.failures = []

    def request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        return self.session.request(method, url, **kwargs)

    def fail(self, message):
        self.failures.append(message)
        print(f"  FAIL: {message}")

    def ok(self, message):
        print(f"  ok:   {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the reviewer password from the first line of stdin.",
    )
    args = parser.parse_args()

    password = (
        sys.stdin.readline().strip()
        if args.password_stdin
        else getpass.getpass("Reviewer password: ")
    )
    if not password:
        print("No password supplied.")
        return 2

    session = httpx.Client(timeout=30)
    checker = Checker(args.base_url, session)

    print(f"Signing in as {args.username} at {args.base_url} ...")
    response = session.post(
        f"{checker.base_url}/auth/login",
        json={"username": args.username, "password": password},
    )
    if response.status_code != 200:
        print(f"Login failed: HTTP {response.status_code} {response.text[:300]}")
        session.close()
        return 2

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        print("Login response did not contain an access token.")
        session.close()
        return 2
    session.headers.update({"Authorization": f"Bearer {token}"})

    print("\nAccount")
    me = checker.request("GET", "/auth/me")
    if me.status_code != 200:
        checker.fail(f"/auth/me returned HTTP {me.status_code}")
    else:
        data = me.json()
        print(f"  username:    {data.get('username')}")
        print(f"  employee_id: {data.get('employee_id')}")
        print(f"  role:        {data.get('role')}")
        print(f"  department:  {data.get('department')}")
        if (data.get("role") or "").upper() != "META_REVIEWER":
            checker.fail("account role is not META_REVIEWER")
        else:
            checker.ok("role is META_REVIEWER")

        permissions = data.get("permissions") or {}
        accessible = sorted(
            key
            for key, value in permissions.items()
            if value.get("has_access")
        )
        print(f"  modules:     {', '.join(accessible) or '(none)'}")
        unexpected = [
            key for key in accessible if key not in {"whatsapp", "whatsapp_connection"}
        ]
        if unexpected:
            checker.fail(f"unexpected module access: {', '.join(unexpected)}")
        else:
            checker.ok("no CRM modules beyond WhatsApp")

    print("\nAllowed WhatsApp surface")
    for path in ALLOWED_GET:
        response = checker.request("GET", path)
        if response.status_code == 403:
            checker.fail(f"GET {path} unexpectedly returned 403")
        elif response.status_code >= 500:
            checker.fail(f"GET {path} returned HTTP {response.status_code}")
        else:
            checker.ok(f"GET {path} -> HTTP {response.status_code}")
            if path == "/whatsapp/conversations" and response.status_code == 200:
                conversations = response.json()
                print(f"        visible conversations: {len(conversations)}")
                if not conversations:
                    print(
                        "        WARNING: the reviewer has no assigned test "
                        "conversation. Assign one before recording."
                    )

    print("\nDenied CRM surface")
    for path in DENIED_GET:
        response = checker.request("GET", path)
        if response.status_code == 403:
            checker.ok(f"GET {path} -> 403")
        else:
            checker.fail(f"GET {path} returned HTTP {response.status_code}, expected 403")

    print("\nDenied onboarding mutations")
    for path, body in DENIED_POST:
        response = checker.request("POST", path, json=body)
        if response.status_code == 403:
            checker.ok(f"POST {path} -> 403")
        else:
            checker.fail(f"POST {path} returned HTTP {response.status_code}, expected 403")

    print("\nSummary")
    session.close()
    if checker.failures:
        print(f"  {len(checker.failures)} check(s) failed.")
        return 1
    print("  All reviewer access checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
