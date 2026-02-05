
# from fastapi.security import OAuth2PasswordBearer
import os
from time import tzname
from zoneinfo import ZoneInfo
from datetime import timedelta, datetime
from jose import jwt
from passlib.context import CryptContext
from .models import TokenData
from typing import Optional
import app.database as database
import redis.asyncio as redis

REDISHOST = os.getenv(key="REDISHOST")
datetime.now(ZoneInfo(tzname[0]))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Authentication():

    def __init__(self):

        self.SECRET_KEY = os.getenv('SECRET_KEY')
        self.ALGORITHM = os.getenv('ALGORITHM')
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
        self.user_storage = database.UserStorage(
            collection_name="user_collection")
        self._redis_conn = None

    def _get_redis_connection(self):
        """Get or create Redis connection for the current event loop."""
        # Create a fresh connection each time to avoid event loop issues
        # This ensures the connection is always attached to the current event loop
        return redis.from_url(
            REDISHOST, encoding="utf-8", decode_responses=True
        )

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
        """ create an access token with an expiry date"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(ZoneInfo("GMT")) + expires_delta
        else:
            expire = datetime.now(ZoneInfo("GMT")) + \
                timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    async def add_blacklist_token(self, token):
        """ add the given token to the blacklist"""
        payload = jwt.decode(token, self.SECRET_KEY,
                             algorithms=[self.ALGORITHM])
        account_id: str = payload.get("sub")
        token_scopes = payload.get("scopes", [])
        expires = payload.get("exp")
        token_data = TokenData(scopes=token_scopes,
                               username=account_id, expires=expires)

        conn = self._get_redis_connection()
        result = await conn.setex(
            token, int((token_data.expires - datetime.now(ZoneInfo("GMT"))).total_seconds()), 1)
        await conn.aclose()
        return result

    async def is_token_blacklisted(self, token):
        """ return true if supplied token is in the blacklist"""
        conn = self._get_redis_connection()
        result = await conn.get(token)
        await conn.aclose()
        return bool(result)
