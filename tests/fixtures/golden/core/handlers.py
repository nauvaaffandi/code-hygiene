"""Framework entry points - Flask and FastAPI handlers."""

from flask import Flask
from fastapi import FastAPI
from fastapi import APIRouter

# Flask app (must be named 'app' to match framework pattern)
app = Flask(__name__)


@app.route("/")
def flask_index():
    return "Flask Hello"


@app.route("/api/users")
def flask_get_users():
    return []


# FastAPI app (must be named 'app' to match framework pattern)
app = FastAPI()


@app.get("/")
def fastapi_root():
    return {"Hello": "World"}


@app.post("/items/")
def fastapi_create_item(item: dict):
    return item


# Also test router pattern
router = APIRouter()


@router.get("/router-test")
def router_test():
    return {"test": True}


def internal_handler():
    """Internal helper - not a route."""
    pass


def unused_handler():
    """Genuinely unused - should be flagged."""
    pass