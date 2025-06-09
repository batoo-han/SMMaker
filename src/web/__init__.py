"""Flask-based web interface for SMMaker."""

from pathlib import Path

from flask import Flask, render_template, request, redirect, session
from passlib.context import CryptContext

from src.db import models

# Initialize Flask app and configuration
app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
app.secret_key = "change_me"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Ensure database tables exist
models.init_db()


def get_db():
    """Return a new database session."""
    return models.SessionLocal()


def get_current_user(db):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


@app.route("/")
def index():
    db = get_db()
    user = get_current_user(db)
    try:
        if user:
            return render_template("dashboard.html", user=user)
        return render_template("login.html")
    finally:
        db.close()


@app.post("/login")
def login():
    db = get_db()
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and pwd_context.verify(password, user.password_hash):
        session["user_id"] = user.id
        db.close()
        return redirect("/")
    db.close()
    return render_template("login.html", error="Неверные данные")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.get("/register")
def register_form():
    return render_template("register.html")


@app.post("/register")
def register():
    db = get_db()
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if db.query(models.User).filter(models.User.username == username).first():
        db.close()
        return render_template("register.html", error="Пользователь существует")
    user = models.User(username=username, password_hash=pwd_context.hash(password))
    db.add(user)
    db.commit()
    session["user_id"] = user.id
    db.close()
    return redirect("/")

