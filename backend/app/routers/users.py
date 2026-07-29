from fastapi import APIRouter, Depends

from ..core.deps import get_current_user
from ..models import User
from ..schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
