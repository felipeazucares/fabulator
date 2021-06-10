
from typing import Optional
from pydantic import BaseModel, Field

# -------------------------------------
#   Classes for http requests
# -------------------------------------


class RequestAddNodeSchema(BaseModel):
    #name: str = Field(...)
    parent: Optional[str] = None
    previous: Optional[str] = None
    next: Optional[str] = None
    description: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[list] = None

    class Config:
        schema_extra = {
            "example": {
                "parent": "8002fa78-ca07-11eb-992a-f01898e87167",
                "previous": "8003fb81-ca07-11eb-992a-f01898e87178",
                "next": "8543fb81-ba08-14ef-992a-f01898e87200",
                "description": "John meets his evil twin in a bar",
                "text": "John walked into the bar. He pulled up a stool and sat down",
                "tags": ['main plot', 'john', 'evil twin']
            }
        }


class RequestUpdateNodeSchema(BaseModel):
    name: Optional[str]
    parent: Optional[str]
    previous: Optional[str]
    next: Optional[str]
    description: Optional[str]
    text: Optional[str]
    tags: Optional[dict]


class NodePayload(BaseModel):
    description: Optional[str] = None
    prev: Optional[str] = None
    next: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[dict] = None


def ResponseModel(data, message):
    return {
        "data": [data],
        "code": 200,
        "message": message,
    }


def ErrorResponseModel(error, code, message):
    return {"error": error, "code": code, "message": message}
