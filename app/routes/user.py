import datetime
import uuid

from fastapi import APIRouter, HTTPException, Request
import jwt

from core.config import settings
from core.database import db
from core.models.user import (
    UserCreateModel,
    UserJwtPayload,
    UserLoginModel,
    UserResponseModel,
)
from core.utils.bcrypt import hash_password, verify_password

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/")
def create_user(user_input: UserCreateModel):
    print("Creating user with input:", user_input.model_dump())
    if db.users.find_one({"email": user_input.email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    user_dict = user_input.model_dump()
    print("Creating user with input:", user_dict)
    name_filtered = user_dict["name"].strip().lower().replace(" ", "_")
    user_dict["name"] = user_dict["name"].strip().title()
    user_dict["password"] = hash_password(user_dict["password"])
    user_dict["userId"] = f"{name_filtered}_{uuid.uuid4().hex[:6]}"
    user_dict["is_active"] = True
    user_dict["threads"] = {}

    result = db.users.insert_one(user_dict)

    print("User created with ID:", result.inserted_id)

    created_user = db.users.find_one(
        {"_id": result.inserted_id}, {"password": 0, "_id": 0}
    )
    return {
        "status": "success",
        "message": "User created successfully",
        "user": UserResponseModel(**created_user),
    }


@router.get("/{user_id}")
def get_user(request: Request, user_id: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    if payload.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied to this user")

    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        print("User not found for userId:", user_id)
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "status": "success",
        "message": "User retrieved successfully",
        "user": user,
    }


@router.post("/login")
def login_user(user_input: UserLoginModel):
    user_data = user_input.model_dump()
    print("Login attempt with input:", user_data)

    user = db.users.find_one({"email": user_data["email"]}, {"_id": 0})
    if not user or not verify_password(user_data["password"], user["password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token_payload = UserJwtPayload(
        userId=user["userId"],
        name=user["name"],
        email=user["email"],
        is_active=user.get("is_active", True),
    ).model_dump()

    # Add expiry — tokens valid for 24 hours
    token_payload["exp"] = datetime.datetime.now(
        datetime.timezone.utc
    ) + datetime.timedelta(hours=24)

    token = jwt.encode(
        token_payload,
        key=settings.SECRET_KEY,
        algorithm="HS256",
    )

    user.pop("password", None)
    print("User logged in successfully:", user["userId"])
    return {
        "status": "success",
        "message": "User logged in successfully",
        "user": user,
        "token": token,
    }
