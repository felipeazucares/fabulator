from datetime import datetime, timezone
from typing import Optional, Annotated
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, StringConstraints
from treelib import Tree
from bson.objectid import ObjectId
from enum import Enum

# ------------------------------------------
#   Input validation limits
# ------------------------------------------
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
NODE_NAME_MAX_LEN = 200
DESCRIPTION_MAX_LEN = 2000
TEXT_MAX_LEN = 50_000
LINK_FIELD_MAX_LEN = 200
TAGS_MAX_COUNT = 50
TAG_MAX_LEN = 100

# Reusable constrained type aliases
UuidStr = Annotated[str, StringConstraints(pattern=UUID_PATTERN, strip_whitespace=True)]
NodeNameStr = Annotated[str, StringConstraints(min_length=1, max_length=NODE_NAME_MAX_LEN, strip_whitespace=True)]
DescriptionStr = Annotated[str, StringConstraints(max_length=DESCRIPTION_MAX_LEN, strip_whitespace=True)]
TextStr = Annotated[str, StringConstraints(max_length=TEXT_MAX_LEN)]
LinkStr = Annotated[str, StringConstraints(max_length=LINK_FIELD_MAX_LEN, strip_whitespace=True)]


def _validate_tags_list(v):
    if v is None:
        return v
    if len(v) > TAGS_MAX_COUNT:
        raise ValueError(f"tags list exceeds maximum of {TAGS_MAX_COUNT} items")
    for tag in v:
        if not isinstance(tag, str):
            raise ValueError("each tag must be a string")
        if len(tag) > TAG_MAX_LEN:
            raise ValueError(f"tag exceeds maximum length of {TAG_MAX_LEN}")
        if len(tag.strip()) == 0:
            raise ValueError("tags must not be empty or whitespace-only")
    return v


# -------------------------------------
#   Classes for http requests
# -------------------------------------


class RequestAddSchema(BaseModel):
    parent: Optional[UuidStr] = None
    previous: Optional[LinkStr] = None
    next: Optional[LinkStr] = None
    description: Optional[DescriptionStr] = None
    text: Optional[TextStr] = None
    tags: Optional[list[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "parent": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "previous": "previous scene",
                "next": "next scene",
                "description": "John meets his evil twin in a bar",
                "text": "John walked into the bar. He pulled up a stool and sat down",
                "tags": ['main plot', 'john', 'evil twin']
            }
        }
    )


class RequestUpdateSchema(BaseModel):
    name: Optional[NodeNameStr] = None
    parent: Optional[UuidStr] = None
    previous: Optional[LinkStr] = None
    next: Optional[LinkStr] = None
    description: Optional[DescriptionStr] = None
    text: Optional[TextStr] = None
    tags: Optional[list[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "An updated node name",
                "parent": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "previous": "previous scene",
                "next": "next scene",
                "description": "John's evil twin escapes into another dimension",
                "text": "There was a strange burning smell coming from the room next door",
                "tags": ['main plot', 'john', 'evil twin', 'Mirror Universe']
            }
        }
    )


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
    description: Optional[DescriptionStr] = None
    previous: Optional[LinkStr] = None
    next: Optional[LinkStr] = None
    text: Optional[TextStr] = None
    tags: Optional[list[str]] = None


class SubTree(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sub_tree: dict

# -------------------------------------
#   Classes for user account
# -------------------------------------


class Name(BaseModel):
    firstname: str
    surname: str


# UserType enum - replaces fastapi-restful CamelStrEnum
class UserType(str, Enum):
    free = "free"
    premium = "premium"


class UserDetails(BaseModel):
    name: Name  # use nested model definition
    username: str
    password: str  # hashed password
    account_id: Optional[str] = None
    email: EmailStr
    disabled: Optional[bool] = False
    user_role: str
    user_type: UserType

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class RetrievedUserDetails(BaseModel):
    id: str
    name: Name  # use nested model definition
    username: str
    account_id: str
    email: EmailStr
    disabled: Optional[bool] = False
    user_role: str
    user_type: UserType

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class UserAccount(BaseModel):
    account_id: str


class UpdateUserDetails(BaseModel):
    name: Optional[Name] = None  # use nested model definition
    email: Optional[EmailStr] = None


class UpdateUserPassword(BaseModel):
    new_password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_password": "a_new_password",
            }
        }
    )


class UpdateUserType(BaseModel):
    user_type: UserType

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_type": "free",
            }
        }
    )


# -------------------------------------
#   Classes for authentication
# -------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: list[str] = []
    expires: datetime


# -------------------------------------
#   Classes for mongo db storage
# -------------------------------------


class TreeSaveSchema():
    def __init__(self, account_id: str, tree: Tree):
        self.account_id = account_id
        self.tree = tree
        self.date_time = datetime.now(timezone.utc)


def saves_helper(save) -> dict:
    return {
        "account_id": str(save["account_id"]),
        "tree": dict(save["tree"]),
        "date_time": str(save["date_time"])
    }


def users_saves_helper(result) -> dict:
    """ converts dict returned to object"""
    return RetrievedUserDetails(
        id=str(ObjectId(result["_id"])),
        name=Name(firstname=str(result["name"]["firstname"]),
                  surname=result["name"]["surname"]),
        username=str(result["username"]),
        account_id=str(result["account_id"]),
        email=result["email"],
        disabled=str(result["disabled"]),
        user_role=str(result["user_role"]),
        user_type=str(result["user_type"])
    )
