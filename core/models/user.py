from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, GetCoreSchemaHandler
from pydantic_core import core_schema

from core.models.thread import ThreadInstruction


class MongoModel(BaseModel):
    model_config = {
        "json_encoders": {ObjectId: str},
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class UserJwtPayload(BaseModel):
    userId: str
    name: str
    email: EmailStr
    is_active: bool = True


class UserCreateModel(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLoginModel(BaseModel):
    email: EmailStr
    password: str


class ThreadDocument(BaseModel):
    docId: str
    title: str
    type: str
    time_uploaded: datetime
    file_name: str


class ChatMessage(BaseModel):
    type: Literal["agent", "user"]
    content: str
    timestamp: datetime


class Thread(BaseModel):
    thread_name: str
    documents: List[ThreadDocument]
    chats: List[ChatMessage]
    instructions: List["ThreadInstruction"] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


from bson import ObjectId
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate_from_mongodb_id(value: Any) -> ObjectId:
            if isinstance(value, ObjectId):
                return value
            if isinstance(value, str):
                if ObjectId.is_valid(value):
                    return ObjectId(value)
            raise ValueError("Invalid ObjectId or string representation of ObjectId")

        return core_schema.no_info_after_validator_function(
            validate_from_mongodb_id,
            core_schema.union_schema(
                [core_schema.is_instance_schema(ObjectId), core_schema.str_schema()]
            ),
            serialization=core_schema.to_string_ser_schema(),
        )


class UserModel(MongoModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    userId: str
    name: str
    email: EmailStr
    password: str
    is_active: bool = True
    threads: Dict[str, Thread] = Field(default_factory=dict)


class UserResponseModel(MongoModel):
    userId: str
    name: str
    email: EmailStr
    is_active: bool = True
    threads: Dict[str, Thread] = Field(default_factory=dict)
