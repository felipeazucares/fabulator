import uuid
import motor.motor_asyncio
from typing import Optional
from treelib import Tree
from fastapi import FastAPI, Body, APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from bson.objectid import ObjectId
from pydantic import BaseModel, Field


from .models import (
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    ResponseModel,
    ErrorResponseModel
)


MONGO_DETAILS = "mongodb://localhost:27017"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.students
student_collection = database.get_collection("students_collection")

# ----------------------------
#   Pydantic models
# ----------------------------


def student_helper(student) -> dict:
    return {
        "id": str(student["_id"]),
        "fullname": student["fullname"],
        "course_of_study": student["course_of_study"],
        "year": student["year"],
        "GPA": student["gpa"],
    }


class PyObjectId(ObjectId):
    @ classmethod
    def __get_validators__(cls):
        yield cls.validate

    @ classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @ classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class StudentSchema(BaseModel):
    fullname: str = Field(...)
    course_of_study: str = Field(...)
    year: int = Field(..., gt=0, lt=9)
    gpa: float = Field(..., le=4.0)

    class Config:
        schema_extra = {
            "example": {
                "fullname": "John Doe",
                "course_of_study": "Water resources engineering",
                "year": 2,
                "gpa": "3.0",
            }
        }


class UpdateStudentModel(BaseModel):
    fullname: Optional[str]
    course_of_study: Optional[str]
    year: Optional[int]
    gpa: Optional[float]

    class Config:
        schema_extra = {
            "example": {
                "fullname": "John Doe",
                "course_of_study": "Water resources and environmental engineering",
                "year": 4,
                "gpa": "4.0",
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


# ----------------------------
#   DB async function calls
# ----------------------------
async def add_student(student_data: dict) -> dict:
    student = await student_collection.insert_one(student_data)
    new_student = await student_collection.find_one({"_id": student.inserted_id})
    return student_helper(new_student)

# Retrieve all students present in the database


async def retrieve_students():
    students = []
    async for student in student_collection.find():
        students.append(student_helper(student))
    return students

# ------------------------
#   FABULATOR
# ------------------------
app = FastAPI()
version = "v.0.0.1"

origins = [
    "http://localhost:8000",
    "localhost:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def initialise_tree():
    tree = Tree()
    return tree


@ app.get("/nodes")
async def get_all_nodes() -> dict:
    tree.show(line_type="ascii-em")
    return tree.all_nodes()


@ app.get("/nodes/{id}")
async def get_a_node() -> dict:
    print(f"id:{id}")
    return tree.get_node(id)


@ app.get("/")
async def get() -> dict:
    return {"message": f"Fabulator {version}"}


@ app.post("/nodes/{name}")
async def create_node(name: str, request: RequestAddSchema = Body(...)) -> dict:
    # map the incoming fields from the https request to the fields required by the treelib API
    request = jsonable_encoder(request)
    print(f"req: {request}")
    node_payload = NodePayload()

    if request["description"]:
        node_payload.description = request["description"]
    if request["next"]:
        node_payload.next = request["next"]
    if request["previous"]:
        node_payload.previous = request["previous"]
    if request["text"]:
        node_payload.text = request["text"]
    if request["tags"]:
        node_payload.tags = request["tags"]

    if request["parent"]:
        new_node = tree.create_node(
            name, parent=request["parent"], data=node_payload)
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            new_node = tree.create_node(
                name, data=node_payload)
        else:
            return {"message": "Tree already has a root node"}
    print(f"new node: {new_node}")
    return{new_node}


@ app.put("/nodes/{id}")
async def update_node(id: str, request: RequestUpdateSchema = Body(...)) -> dict:
    # generate a new id for the node if we have a parent
    print(f"req: {request}")
    node_payload = NodePayload(description=request.description,
                               previous=request.previous, next=request.next, tags=request.tags, text=request.text)
    if request.name:
        update_node = tree.update_node(
            id, _tag=request.name, data=node_payload)
    else:
        update_node = tree.update_node(
            id, data=node_payload)
    print(f"updated node: {update_node }")
    return{update_node}


@ app.delete("/nodes/{id}")
async def delete_node(id: str) -> dict:
    # remove the node with the supplied id
    # probably want to stash the children somewhere first in a sub tree for later use
    response = tree.remove_node(id)
    return response


# -------------------
# student routes
# -------------------

@ app.post("/student", response_description="Student data added into the database")
async def add_student_data(student: StudentSchema = Body(...)):
    student = jsonable_encoder(student)
    new_student = await add_student(student)
    return ResponseModel(new_student, "Student added successfully.")


@ app.get("/students", response_description="Students retrieved")
async def get_students():
    students = await retrieve_students()
    if students:
        return ResponseModel(students, "Students data retrieved successfully")
    return ResponseModel(students, "Empty list returned")

# Create tree
tree = initialise_tree()
