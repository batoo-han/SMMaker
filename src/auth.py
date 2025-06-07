from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
import json
import os
import subprocess
from typing import Dict

USERS_FILE = "users.json"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


def load_users() -> Dict[str, Dict]:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: Dict[str, Dict]):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)


def run_app_with_settings(settings: Dict[str, str]):
    env = os.environ.copy()
    env.update(settings)
    subprocess.Popen(["python", "src/main.py"], env=env)


class RegisterData(BaseModel):
    username: str
    password: str
    settings: Dict[str, str] = {}


class LoginData(BaseModel):
    username: str
    password: str


@app.post("/register")
def register(data: RegisterData):
    users = load_users()
    if data.username in users:
        raise HTTPException(status_code=400, detail="User already exists")
    users[data.username] = {
        "password_hash": pwd_context.hash(data.password),
        "settings": data.settings,
    }
    save_users(users)
    return {"status": "registered"}


@app.post("/login")
def login(data: LoginData):
    users = load_users()
    user = users.get(data.username)
    if not user or not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    run_app_with_settings(user.get("settings", {}))
    return {"status": "started"}
