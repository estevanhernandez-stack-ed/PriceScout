from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app import users
from api.routers.auth import get_current_user

router = APIRouter()

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class PasswordResetRequest(BaseModel):
    username: str

class PasswordResetWithCode(BaseModel):
    username: str
    code: str
    new_password: str

@router.post("/users/change-password", tags=["Users"])
async def change_password(password_data: PasswordChange, current_user: users.User = Depends(get_current_user)):
    success, message = users.change_password(current_user['username'], password_data.old_password, password_data.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}

@router.post("/users/reset-password-request", tags=["Users"])
async def reset_password_request(request_data: PasswordResetRequest):
    success, code_or_message = users.generate_reset_code(request_data.username)
    if success:
        # In a real app, you'd email this code. For now, we return it.
        return {"message": "Reset code generated.", "code": code_or_message}
    else:
        # Don't reveal if the user exists
        return {"message": "If a user with that email exists, a reset code has been sent."}

@router.post("/users/reset-password-with-code", tags=["Users"])
async def reset_password_with_code(reset_data: PasswordResetWithCode):
    success, message = users.reset_password_with_code(reset_data.username, reset_data.code, reset_data.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}
