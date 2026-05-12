from typing import Optional

from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    fullname: Optional[str] =  None

class UserRegisterResponse(BaseModel):
    email: EmailStr
    fullname: Optional[str] = None

class UserLogin(BaseModel):
    username: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    id: str