
from typing import Optional
from pydantic import BaseModel, Field

# -------------------------------------
#   Classes for http requests
# -------------------------------------


class RequestAddNodeSchema(BaseModel):
    id: str = Field(...)
    name: str = Field(...)
    parent: Optional[str]
    previous: Optional[str]
    next: Optional[str]
    description: Optional[str]
    text: Optional[str]
    tags: Optional[dict]


class RequestUpdateNodeSchema(BaseModel):
    id: str = Field(...)
    name: Optional[str]
    parent: Optional[str]
    previous: Optional[str]
    next: Optional[str]
    description: Optional[str]
    text: Optional[str]
    tags: Optional[dict]


def ResponseModel(data, message):
    return {
        "data": [data],
        "code": 200,
        "message": message,
    }


def ErrorResponseModel(error, code, message):
    return {"error": error, "code": code, "message": message}
