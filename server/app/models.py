from datetime import date, datetime, time, timedelta
from hashlib import sha256
from typing import Dict, Optional
from pydantic import BaseModel, Field, ValidationError, validator
from treelib import Tree
import uuid

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


def ResponseModel(data, message):
    return {
        "data": [data],
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


# -------------------------------------
#   Classes for user account
# -------------------------------------

class Name(BaseModel):
    firstname: str
    surname: str


class UserDetails(BaseModel):
    name: Name
    username: str
    account_id: str


class User():
    def __init__(self, username: str, firstname: str, surname: str):
        self.accountid = uuid.uuid4(username)
        self.username = username
        self.name = {self.firstname: firstname, self.surname: surname}

# -------------------------------------
#   Classes for mongo db storage
# -------------------------------------


class TreeSchema():
    def __init__(self, tree: Tree):
        self.account = str
        self.tree = tree
        self.date_time = datetime.utcnow()


def saves_helper(save) -> dict:
    return {
        "account": str(["user"]),
        "tree": str(save["tree"]),
        "date_time": str(save["date_time"])
    }
