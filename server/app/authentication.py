
from fastapi.security import OAuth2PasswordBearer
from time import tzname
from pytz import timezone
from datetime import timedelta, datetime
from jose import jwt
from passlib.context import CryptContext
# from .models import UserDetails
from typing import Optional
import app.database as database
import os
import redis

timezone(tzname[0]).localize(datetime.now())
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Authentication():

    def __init__(self):

        self.SECRET_KEY = os.getenv('SECRET_KEY')
        self.ALGORITHM = os.getenv('ALGORITHM')
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
        self.user_storage = database.UserStorage(
            collection_name="user_collection")
        self.conn = redis.Redis()

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
            expire = datetime.now(timezone("gmt")) + expires_delta
        else:
            expire = datetime.now(timezone("gmt")) + \
                timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def init_blacklist_file(self):
        open('blacklist_db.txt', 'a').close()
        return True

    def add_blacklist_token(self, token):
        result = self.conn.lpush("token", token)

        print(f"llen:{self.conn.llen('token')}")
        print(f"result:{result}")
        return result

    def is_token_blacklisted(self, token):
        blacklist = self.conn.lrange(
            name=token, start=0, end=self.conn.llen("token"))

        print(f"blacklist:{blacklist}")
        if(token in blacklist):
            return True
        else:
            return False
