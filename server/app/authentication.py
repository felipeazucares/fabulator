
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from .models import UserDetails
from typing import Optional
import app.database as database
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="get_token")


class Authentication():

    def __init__(self):

        self.SECRET_KEY = os.getenv('SECRET_KEY')
        self.ALGORITHM = os.getenv('ALGORITHM')
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
        self.user_storage = database.UserStorage(
            collection_name="user_collection")

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return pwd_context.hash(password)

    async def get_user_by_username(self, username: str):
        """ returns the details for a given userid """
        return(await self.user_storage.get_user_details_by_username(username=username))

    async def get_user_by_account_id(self, account_id: str):
        """ returns the details for a given account_id """
        return(await self.user_storage.get_user_details_by_account_id(account_id=account_id))

    async def authenticate_user(self, username: str, password: str):
        """ passed a db of users & username and input password, verifies password - returns user"""
        user = await self.get_user_by_username(username)
        if not user:
            return False
        if not self.verify_password(password, user.password):
            return False
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt
