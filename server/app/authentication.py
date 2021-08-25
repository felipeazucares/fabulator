from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from .models import UserInDB, TokenData, UserDetails
from typing import Optional
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="authenticate")


class Authentication():

    def __init__(self):

        self.SECRET_KEY = os.getenv('SECRET_KEY')
        self.ALGORITHM = os.getenv('ALGORITHM')
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return pwd_context.hash(password)

    def get_user_func(self, db, username: str):
        if username in db:
            user_dict = db[username]
            return UserInDB(**user_dict)

    def authenticate_user(self, db, username: str, password: str):
        user = self.get_user_func(db, username)
        if not user:
            return False
        if not self.verify_password(password, user.hashed_password):
            return False
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    async def get_current_user(self, token: str = Depends(oauth2_scheme)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.SECRET_KEY,
                                 algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception
        user = self.get_user_func(
            fake_users_db, username=token_data.username)
        if user is None:
            raise credentials_exception
        return user

    async def get_current_active_user(self, current_user: UserDetails = Depends(get_current_user)):
        if current_user.disabled:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user
