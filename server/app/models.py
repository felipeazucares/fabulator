from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, validator, ValidationError
from redis.client import string_keys_to_dict
from treelib import Tree
from bson.objectid import ObjectId
from enum import auto
from fastapi_restful.enums import CamelStrEnum


# -------------------------------------
#   Classes for http requests
# -------------------------------------


class RequestAddSchema(BaseModel):
    parent: Optional[str] = None
    previous: Optional[str] = None
    next: Optional[str] = None
    description: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[list] = None

    class Config:
        schema_extra = {
            "example": {
                "parent": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "previous": "308fdfae-ca09-11eb-b437-f01898e87167",
                "next": "308fdfae-ca09-11eb-b437-f01898e87167",
                "description": "John meets his evil twin in a bar",
                "text": "John walked into the bar. He pulled up a stool and sat down",
                "tags": ['main plot', 'john', 'evil twin']
            }
        }


class RequestUpdateSchema(BaseModel):
    name: Optional[str] = None
    parent: Optional[str] = None
    previous: Optional[str] = None
    next: Optional[str] = None
    description: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[list] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "An updated node name",
                "parent": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "previous": "308fdfae-ca09-11eb-b437-f01898e87167",
                "next": "308fdfae-ca09-11eb-b437-f01898e87167",
                "description": "John's evil twin escapes into another dimension",
                "text": "There was a strange burning smell coming from the room next door",
                "tags": ['main plot', 'john', 'evil twin', 'Mirror Universe']
            }
        }


class ResponseModel2(BaseModel):
    data: Optional[dict] = None
    code: int
    message: str


def ResponseModel(data, message):
    return {
        "data": data,
        "code": 200,
        "message": message,
    }


def ErrorResponseModel(error, code, message):
    return {"error": error, "code": code, "message": message}

# -------------------------------------
#   Classes for tree node data
# -------------------------------------


class NodePayload(BaseModel):
    description: Optional[str] = None
    previous: Optional[str] = None
    next: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[list] = None


class SubTree(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    sub_tree: dict

# -------------------------------------
#   Classes for Projects
# -------------------------------------


class CreateProject(BaseModel):
    """ model for user data input"""
    name: str
    description: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "My new project name",
                "description": "My new project description"
            }
        }


class RetrieveProject(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    create_date: datetime
    modified_date: datetime


class UpdateProject(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "My updated project name",
                "description": "My updated project description"
            }
        }


# -------------------------------------
#   Classes for user account
# -------------------------------------


class Name(BaseModel):
    firstname: str
    surname: str


class UserType(CamelStrEnum):
    free = auto()
    premium = auto()


class UserDetails(BaseModel):
    name: Name  # use nested model definition
    username: str
    password: str  # hashed password
    account_id: Optional[str] = None
    email: EmailStr
    disabled: Optional[bool] = False
    user_role: str
    user_type: UserType

    class Config:
        schema_extra = {
            "example": {
                "name": {"firstname": "Alexei", "surname": "Guinness"},
                "username": "a_dummy_user",
                "password": "us3Th3F0rceLuk3",
                "account_id": "308fdfae-ca09-11eb-b437-f01898e87167",
                "email": "ben@kenobi.com",
                "disabled": False,
                "user_role": "user:reader,user:writer,tree:reader,tree:writer",
                "user_type": "free"
            }
        }


class RetrievedUserDetails(BaseModel):
    id: str
    name: Name  # use nested model definition
    username: str
    account_id: str
    email: EmailStr
    disabled: Optional[bool] = False
    user_role: str
    user_type: UserType

    class Config:
        schema_extra = {
            "example": {
                "name": {"firstname": "Alexei", "surname": "Guinness"},
                "username": "a_dummy_user",
                "account_id": "308fdfae-ca09-11eb-b437-f01898e87167",
                "email": "ben@kenobi.com",
                "disabled": False,
                "user_role": "user:reader,user:writer,tree:reader,tree:writer",
                "user_type": "free"
            }
        }


class UserDetailsError(BaseModel):
    error: str
    message: str


class UserAccount(BaseModel):
    account_id: str


class UpdateUserDetails(BaseModel):
    name: Optional[Name]  # use nested model definition
    email: Optional[EmailStr]


class UpdateUserPassword(BaseModel):
    new_password: str

    class Config:
        schema_extra = {
            "example": {
                "new_password": "a_new_password",
            }
        }


class UpdateUserType(BaseModel):
    user_type: UserType

    class Config:
        schema_extra = {
            "example": {
                "user_type": "free",
            }
        }


# -------------------------------------
#   Classes for authentication
# -------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []
    expires: datetime


# -------------------------------------
#   Classes for mongo db storage
# -------------------------------------


class TreeSaveSchema():
    def __init__(self, account_id: str, tree: Tree):
        self.account_id = account_id
        self.tree = tree
        self.date_time = datetime.utcnow()


def saves_helper(save) -> dict:
    return {
        "account_id": str(save["account_id"]),
        "tree": dict(save["tree"]),
        "date_time": str(save["date_time"])}


def users_saves_helper(result) -> dict:
    """ converts dict returned to object"""
    return RetrievedUserDetails(
        id=str(ObjectId(result["_id"])),
        name=Name(firstname=str(result["name"]["firstname"]),
                  surname=result["name"]["surname"]),
        username=str(result["username"]),
        account_id=str(result["account_id"]),
        email=EmailStr(result["email"]),
        disabled=str(result["disabled"]),
        user_role=str(result["user_role"]),
        user_type=str(result["user_type"])
    )


def users_errors_helper(result):
    """ converts dict to object """
    return UserDetailsError(
        error=result["error"],
        message=result["message"]
    )
