"""Deleting a signed-in user's account (withdrawal), with everything kept about them.

Deleting the auth user cascades to every table that holds their data (profiles, consents,
trips -> days -> activities -> preferences, recovery results: migrations 0001 and 0003, all
`on delete cascade`). The usage counts are keyed by a text subject, not a foreign key, so they
are deleted here first. Needs the service key: never reachable from the browser directly.
"""


def delete_account(user_id: str, client) -> None:
    """Raises on failure; the account then still exists and the user can try again."""
    client.table("usage_daily").delete().eq("subject", f"user:{user_id}").execute()
    client.auth.admin.delete_user(user_id)
