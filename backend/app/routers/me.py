import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db.client import MissingConfigError, get_client
from app.routers.deps import Caller, get_caller
from app.services.account import delete_account

router = APIRouter(prefix="/me", tags=["me"])
log = logging.getLogger(__name__)


def get_admin_client():
    try:
        return get_client()
    except MissingConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.delete("", status_code=204, response_class=Response)
def delete_me(
    caller: Annotated[Caller, Depends(get_caller)],
    client: Annotated[object, Depends(get_admin_client)],
) -> Response:
    """Withdraw: delete the signed-in caller's account and all their data. Only ever their own:
    the id comes from the verified token, never from the request."""
    if caller.user_id is None:
        raise HTTPException(status_code=401, detail="sign in to delete your account")
    try:
        delete_account(caller.user_id, client)
    except Exception as e:
        log.exception("account deletion failed for %s", caller.user_id)
        raise HTTPException(status_code=502, detail="could not delete the account") from e
    return Response(status_code=204)
