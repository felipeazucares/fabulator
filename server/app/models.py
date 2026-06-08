from datetime import datetime, timezone
from typing import Optional, Annotated
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, StringConstraints
from bson.objectid import ObjectId
from enum import Enum
from treelib import Tree

# ------------------------------------------
#   Input validation limits
# ------------------------------------------
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
NODE_NAME_MAX_LEN = 200
TITLE_MAX_LEN = 200
AUTHOR_MAX_LEN = 200
DESCRIPTION_MAX_LEN = 2000
TEXT_MAX_LEN = 50_000
LINK_FIELD_MAX_LEN = 200
TAGS_MAX_COUNT = 50
TAG_MAX_LEN = 100

# Reusable constrained type aliases
UuidStr = Annotated[str, StringConstraints(pattern=UUID_PATTERN, strip_whitespace=True)]
NodeNameStr = Annotated[str, StringConstraints(min_length=1, max_length=NODE_NAME_MAX_LEN, strip_whitespace=True)]
TitleStr = Annotated[str, StringConstraints(min_length=1, max_length=TITLE_MAX_LEN, strip_whitespace=True)]
AuthorStr = Annotated[str, StringConstraints(max_length=AUTHOR_MAX_LEN, strip_whitespace=True)]
TagFieldStr = Annotated[str, StringConstraints(min_length=1, max_length=TAG_MAX_LEN, strip_whitespace=True)]
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


class UserDetailsSafe(BaseModel):
    name: Name
    username: str
    account_id: Optional[str] = None
    email: EmailStr
    disabled: Optional[bool] = False
    user_role: str
    user_type: UserType

    model_config = ConfigDict(
        from_attributes=True
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


# -----------------------------------------------
#   Normalised model — enums
# -----------------------------------------------

class NodeType(str, Enum):
    part = "part"
    chapter = "chapter"
    scene = "scene"
    beat = "beat"


# -----------------------------------------------
#   Normalised model — Work schemas
# -----------------------------------------------

class CreateWorkRequest(BaseModel):
    title: TitleStr
    description: Optional[DescriptionStr] = None
    author: Optional[AuthorStr] = None
    tags: Optional[list[str]] = []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "My Novel",
                "description": "A story about remarkable things",
                "author": "Philip Suggars",
                "tags": ["fiction", "drama"]
            }
        }
    )


class UpdateWorkRequest(BaseModel):
    title: Optional[TitleStr] = None
    description: Optional[DescriptionStr] = None
    author: Optional[AuthorStr] = None
    tags: Optional[list[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "My Novel — Revised",
                "author": "Philip Suggars"
            }
        }
    )


class WorkResponse(BaseModel):
    work_id: str
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "work_id": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "title": "My Novel",
                "description": "A story about remarkable things",
                "author": "Philip Suggars",
                "tags": ["fiction"],
                "created_at": "2026-06-07T09:00:00Z",
                "updated_at": "2026-06-07T09:00:00Z"
            }
        }
    )


# -----------------------------------------------
#   Normalised model — Node schemas
# -----------------------------------------------

class CreateNodeRequest(BaseModel):
    work_id: UuidStr
    node_type: NodeType
    parent_id: Optional[UuidStr] = None
    tag: TagFieldStr
    description: Optional[DescriptionStr] = None
    text: Optional[TextStr] = None
    previous: Optional[LinkStr] = None
    next: Optional[LinkStr] = None
    tags: Optional[list[str]] = []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "work_id": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "node_type": "chapter",
                "parent_id": "a11b2c3d-0000-0000-0000-f01898e87167",
                "tag": "Chapter 1",
                "description": "The hero arrives in a strange town",
                "text": "It was a dark and stormy night...",
                "previous": "Prologue",
                "next": "Chapter 2",
                "tags": ["main plot", "introduction"]
            }
        }
    )


class UpdateNodeRequest(BaseModel):
    tag: Optional[TagFieldStr] = None
    parent_id: Optional[UuidStr] = None
    description: Optional[DescriptionStr] = None
    text: Optional[TextStr] = None
    previous: Optional[LinkStr] = None
    next: Optional[LinkStr] = None
    tags: Optional[list[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return _validate_tags_list(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tag": "Chapter 1 — Revised",
                "description": "Updated description"
            }
        }
    )


class ReorderRequest(BaseModel):
    position: int

    @field_validator("position")
    @classmethod
    def validate_position(cls, v):
        if v < 0:
            raise ValueError("position must be a non-negative integer")
        return v

    model_config = ConfigDict(
        json_schema_extra={"example": {"position": 2}}
    )


class NodeResponse(BaseModel):
    node_id: str
    work_id: str
    author: Optional[str] = None
    node_type: NodeType
    parent_id: Optional[str] = None
    position: int
    tag: str
    description: Optional[str] = None
    text: Optional[str] = None
    previous: Optional[str] = None
    next: Optional[str] = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "b33f4e56-ca11-11eb-b437-f01898e87167",
                "work_id": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "author": "Philip Suggars",
                "node_type": "chapter",
                "parent_id": "a11b2c3d-0000-0000-0000-f01898e87167",
                "position": 0,
                "tag": "Chapter 1",
                "description": "The hero arrives",
                "text": "It was a dark and stormy night...",
                "previous": "Prologue",
                "next": "Chapter 2",
                "tags": ["main plot"],
                "created_at": "2026-06-07T09:00:00Z",
                "updated_at": "2026-06-07T09:00:00Z"
            }
        }
    )


# -----------------------------------------------
#   Normalised model — composite response schemas
# -----------------------------------------------

class AncestorsResponse(BaseModel):
    ancestors: list[NodeResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ancestors": []
            }
        }
    )


class WorkStatsResponse(BaseModel):
    work_id: str
    total_nodes: int
    by_type: dict[str, int]
    max_depth: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "work_id": "d22e5e28-ca11-11eb-b437-f01898e87167",
                "total_nodes": 12,
                "by_type": {"part": 2, "chapter": 4, "scene": 4, "beat": 2},
                "max_depth": 3
            }
        }
    )
