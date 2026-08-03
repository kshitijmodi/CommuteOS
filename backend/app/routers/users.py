from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User
from ..schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


class FcmTokenUpdate(BaseModel):
    fcm_token: str


@router.put("/me/fcm-token", response_model=UserRead)
def update_fcm_token(
    payload: FcmTokenUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registers this device's push token so the commute-notification job
    (jobs/send_commute_notifications.py) can actually reach the user. Set
    by the app once it obtains a token from its push provider (currently
    stubbed - see notify_service.py's docstring) after the user opts in.
    """
    current_user.fcm_token = payload.fcm_token
    db.commit()
    db.refresh(current_user)
    return current_user
