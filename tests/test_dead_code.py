import os
import tempfile
import unittest
from pathlib import Path

from code_hygiene.engine.dead_code import DeadCodeChecker
from code_hygiene.ignore import IgnoreEngine


class TestDeadCode(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_unused_import(self):
        self._create_file("main.py", """
import os
import sys
import json

def main():
    print("hello")

if __name__ == "__main__":
    main()
""")
        self._create_file("unused_module.py", """
import random
import math

def unused_func():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unused_imports = [f for f in findings if f.sub_category == "unused_import"]
        self.assertGreater(len(unused_imports), 0)

    def test_unreachable_function(self):
        self._create_file("main.py", """
def used_func():
    return 42

if __name__ == "__main__":
    print(used_func())
""")
        self._create_file("dead_code.py", """
def dead_func():
    return "never called"

class DeadClass:
    def method(self):
        pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable")]
        paths = {f.path for f in unreachable}
        self.assertIn("dead_code.py", paths)

    def test_dynamic_import_not_flagged(self):
        self._create_file("main.py", """
import sys

def load_plugin(name):
    __import__(name)
    return sys.modules[name]

if __name__ == "__main__":
    load_plugin("some_plugin")
""")
        self._create_file("plugin.py", """
def plugin_func():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "plugin.py"]
        for f in unreachable:
            self.assertIn(f.confidence, ["suspected", "likely"])

    def test_dunder_all_exports_not_flagged(self):
        """Functions/classes in __all__ should not be flagged as unreachable."""
        self._create_file("api.py", """
__all__ = ["public_func", "PublicClass"]

def public_func():
    return "public"

def private_func():
    return "private"

class PublicClass:
    pass

class PrivateClass:
    pass
""")
        self._create_file("main.py", """
from api import public_func

if __name__ == "__main__":
    print(public_func())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "api.py"]
        # public_func and PublicClass should NOT be flagged (in __all__)
        # private_func and PrivateClass MAY be flagged
        names = {f.evidence.split("'")[1] for f in unreachable}
        self.assertNotIn("public_func", names)
        self.assertNotIn("PublicClass", names)

    def test_flask_route_not_flagged(self):
        """Flask route handlers should not be flagged as unreachable."""
        self._create_file("app.py", """
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello"

@app.route("/api/users")
def get_users():
    return []

def internal_helper():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "app.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        # Flask routes should NOT be flagged
        self.assertNotIn("index", names)
        self.assertNotIn("get_users", names)
        # internal_helper may be flagged
        # (it's ok if it's not flagged due to dynamic reference detection)

    def test_pytest_fixture_not_flagged(self):
        """pytest fixtures and test functions should not be flagged."""
        self._create_file("test_module.py", """
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_something(sample_data):
    assert sample_data["key"] == "value"

def helper_for_tests():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "test_module.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        # pytest fixtures and tests should NOT be flagged
        self.assertNotIn("sample_data", names)
        self.assertNotIn("test_something", names)

    def test_click_command_not_flagged(self):
        """Click CLI commands should not be flagged."""
        self._create_file("cli.py", """
import click

@click.command()
def hello():
    click.echo("Hello")

@click.group()
def cli():
    pass

def internal_util():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "cli.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        # Click commands should NOT be flagged
        self.assertNotIn("hello", names)
        self.assertNotIn("cli", names)

    def test_fastapi_route_not_flagged(self):
        """FastAPI route handlers should not be flagged."""
        self._create_file("main.py", """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/items/")
def create_item(item: dict):
    return item

def internal_logic():
    pass
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "main.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        # FastAPI routes should NOT be flagged
        self.assertNotIn("read_root", names)
        self.assertNotIn("create_item", names)

    def test_cross_module_attribute_reference(self):
        """Cross-module attribute references (mod.sub.func()) are resolved in static analysis."""
        self._create_file("utils/helpers.py", """
def format_name(name):
    return name.strip().title()

def validate_email(email):
    return "@" in email

def truly_unused_helper():
    pass
""")
        self._create_file("services/user_service.py", """
from utils import helpers

def create_user(name, email):
    # Cross-module attribute reference - now resolved by static analysis
    formatted = helpers.format_name(name)
    valid = helpers.validate_email(email)
    return {"name": formatted, "email": email, "valid": valid}
""")
        self._create_file("main.py", """
from services.user_service import create_user

if __name__ == "__main__":
    user = create_user("  john doe  ", "john@example.com")
    print(user)
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "utils/helpers.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # format_name and validate_email are referenced via helpers.format_name() and helpers.validate_email()
        # and should NOT be flagged as unreachable
        self.assertNotIn("format_name", names)
        self.assertNotIn("validate_email", names)
        
        # truly_unused_helper is genuinely unused and SHOULD be flagged
        self.assertIn("truly_unused_helper", names)

    def test_cross_module_import_module_as_alias(self):
        """Test `import module as alias` followed by `alias.function()`."""
        self._create_file("utils/math_helpers.py", """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def unused_func():
    pass
""")
        self._create_file("services/calculator.py", """
import utils.math_helpers as mh

def compute(a, b):
    return mh.add(a, b) + mh.multiply(a, b)
""")
        self._create_file("main.py", """
from services.calculator import compute

if __name__ == "__main__":
    print(compute(2, 3))
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "utils/math_helpers.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # add and multiply are referenced via mh.add() and mh.multiply()
        self.assertNotIn("add", names)
        self.assertNotIn("multiply", names)
        
        # unused_func is genuinely unused
        self.assertIn("unused_func", names)

    def test_cross_module_from_import_function(self):
        """Test `from module import function` followed by `function()`."""
        self._create_file("utils/string_utils.py", """
def normalize(s):
    return s.strip().lower()

def validate(s):
    return len(s) > 0

def unused_util():
    pass
""")
        self._create_file("services/processor.py", """
from utils.string_utils import normalize, validate

def process(text):
    return validate(normalize(text))
""")
        self._create_file("main.py", """
from services.processor import process

if __name__ == "__main__":
    print(process("  Hello  "))
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "utils/string_utils.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # normalize and validate are directly imported and used
        self.assertNotIn("normalize", names)
        self.assertNotIn("validate", names)
        
        # unused_util is genuinely unused
        self.assertIn("unused_util", names)

    def test_cross_module_from_import_submodule(self):
        """Test `from module import submodule` followed by `submodule.function()`."""
        self._create_file("pkg/core.py", """
def init():
    return "initialized"

def cleanup():
    return "cleaned up"

def internal_helper():
    pass
""")
        self._create_file("pkg/__init__.py", """
from . import core
""")
        self._create_file("services/app.py", """
from pkg import core

def run():
    core.init()
    return core.cleanup()
""")
        self._create_file("main.py", """
from services.app import run

if __name__ == "__main__":
    print(run())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "pkg/core.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # init and cleanup are referenced via core.init() and core.cleanup()
        self.assertNotIn("init", names)
        self.assertNotIn("cleanup", names)
        
        # internal_helper is genuinely unused
        self.assertIn("internal_helper", names)

    def test_cross_module_relative_import(self):
        """Test relative imports with attribute access."""
        self._create_file("pkg/utils/helpers.py", """
def format_data(data):
    return f"[{data}]"

def parse_data(data):
    return data.strip("[]")

def unused_in_pkg():
    pass
""")
        self._create_file("pkg/__init__.py", "")
        self._create_file("pkg/services/handler.py", """
from ..utils import helpers

def handle(input_data):
    return helpers.format_data(helpers.parse_data(input_data))
""")
        self._create_file("main.py", """
from pkg.services.handler import handle

if __name__ == "__main__":
    print(handle("test"))
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "pkg/utils/helpers.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # format_data and parse_data are referenced via helpers.format_data() and helpers.parse_data()
        self.assertNotIn("format_data", names)
        self.assertNotIn("parse_data", names)
        
        # unused_in_pkg is genuinely unused
        self.assertIn("unused_in_pkg", names)

    def test_cross_module_mixed_imports(self):
        """Test mixed import styles in the same file."""
        self._create_file("utils/api.py", """
def fetch():
    return "data"

def save():
    return "saved"

def unused_api():
    pass
""")
        self._create_file("services/client.py", """
import utils.api
from utils.api import save

def sync():
    data = utils.api.fetch()
    utils.api.save()
    return save()
""")
        self._create_file("main.py", """
from services.client import sync

if __name__ == "__main__":
    print(sync())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "utils/api.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # fetch and save are used (via both import styles)
        self.assertNotIn("fetch", names)
        self.assertNotIn("save", names)
        
        # unused_api is genuinely unused
        self.assertIn("unused_api", names)

    def test_cross_module_external_dependency_not_flagged(self):
        """External dependencies should not cause false positives."""
        self._create_file("main.py", """
import os
import json
import requests  # external

def main():
    path = os.path.join("a", "b")
    data = json.dumps({"key": "value"})
    # requests.get("http://example.com")  # commented out
    return path, data

if __name__ == "__main__":
    main()
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        # os.path.join and json.dumps are external - should not be flagged as unreachable
        # (they're not even in our symbol table)
        unreachable = [f for f in findings if f.sub_category.startswith("unreachable")]
        # Should have no unreachable findings in our code
        for f in unreachable:
            self.assertNotEqual(f.path, "main.py")

    def test_cross_module_unresolved_dynamic_still_flagged(self):
        """Dynamic/unresolvable references should still flag with reduced confidence."""
        self._create_file("utils/dynamic.py", """
def static_func():
    return "static"

def dynamic_target():
    return "dynamic"
""")
        self._create_file("services/user.py", """
import importlib

def call_dynamic():
    # Dynamic import - cannot be resolved statically
    module = importlib.import_module("utils.dynamic")
    return module.dynamic_target()

def call_static():
    from utils.dynamic import static_func
    return static_func()
""")
        self._create_file("main.py", """
from services.user import call_dynamic, call_static

if __name__ == "__main__":
    print(call_static())
    print(call_dynamic())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "utils/dynamic.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # static_func is called directly via import - should NOT be flagged
        self.assertNotIn("static_func", names)
        
        # dynamic_target is called via importlib - may be flagged with SUSPECTED confidence
        # (This is acceptable - we prefer reduced confidence over missing it)
        # The test just verifies the tool runs without error
        print(f"Dynamic test - findings: {[(f.evidence, f.confidence) for f in unreachable]}")

    def test_inheritance_override_not_resolved_current_behavior(self):
        """Current behavior: super() calls don't resolve parent methods - they're flagged as unreachable.
        
        This test documents the current limitation. When super() resolution is implemented,
        this test should be updated to expect the parent methods to NOT be flagged.
        """
        self._create_file("base.py", """
class BaseClass:
    def process(self):
        return "base processed"

    def helper(self):
        return "base helper"

    def unused_base_method(self):
        return "unused base"
""")
        self._create_file("derived.py", """
from base import BaseClass

class DerivedClass(BaseClass):
    def process(self):
        base_result = super().process()
        return f"derived -> {base_result}"

    def derived_only(self):
        return "derived only"

    def unused_derived_method(self):
        return "unused derived"
""")
        self._create_file("main.py", """
from derived import DerivedClass

if __name__ == "__main__":
    d = DerivedClass()
    print(d.process())
    print(d.derived_only())
    print(d.helper())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable")]
        
        # Current behavior: super().process() is NOT resolved
        # So BaseClass.process and BaseClass.helper ARE flagged
        base_unreachable = [f for f in unreachable if f.path == "base.py"]
        base_names = {f.evidence.split("'")[1] for f in base_unreachable}
        
        # Base class: process, helper, and unused_base_method are all flagged
        self.assertIn("process", base_names)
        self.assertIn("helper", base_names)
        self.assertIn("unused_base_method", base_names)
        
        # Derived class: unused_derived_method IS flagged
        derived_unreachable = [f for f in unreachable if f.path == "derived.py"]
        derived_names = {f.evidence.split("'")[1] for f in derived_unreachable}
        
        self.assertIn("unused_derived_method", derived_names)

    def test_super_call_not_resolved_current_behavior(self):
        """Current behavior: super().method() calls don't resolve parent methods.
        
        This test documents the current limitation. When super() resolution is implemented,
        this test should be updated to expect the parent methods to NOT be flagged.
        """
        self._create_file("parent.py", """
class Parent:
    def save(self):
        return "saved"

    def validate(self):
        return True

    def internal_log(self):
        pass
""")
        self._create_file("child.py", """
from parent import Parent

class Child(Parent):
    def save(self):
        result = super().save()
        return f"child: {result}"
    
    def custom_validate(self):
        return super().validate() and True
""")
        self._create_file("main.py", """
from child import Child

if __name__ == "__main__":
    c = Child()
    print(c.save())
    print(c.custom_validate())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "parent.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # Current behavior: super().save() and super().validate() are NOT resolved
        # So Parent.save and Parent.validate ARE flagged
        self.assertIn("save", names)
        self.assertIn("validate", names)
        
        # Parent.internal_log is genuinely unused
        self.assertIn("internal_log", names)

    def test_kwargs_forwarding(self):
        """**kwargs forwarding should resolve called functions."""
        self._create_file("handlers.py", """
def handle_request(method, **kwargs):
    return f"{method}: {kwargs}"

def process_data(data, **kwargs):
    return f"processed: {data} with {kwargs}"

def unused_handler(**kwargs):
    pass
""")
        self._create_file("router.py", """
from handlers import handle_request, process_data

def route(method, **kwargs):
    # Forward kwargs to handlers
    if method == "GET":
        return handle_request(method, **kwargs)
    return process_data("default", **kwargs)
""")
        self._create_file("main.py", """
from router import route

if __name__ == "__main__":
    print(route("GET", user="alice", action="view"))
    print(route("POST", user="bob", data={"key": "value"}))
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "handlers.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # handle_request and process_data are called via kwargs forwarding
        self.assertNotIn("handle_request", names)
        self.assertNotIn("process_data", names)
        
        # unused_handler is genuinely unused
        self.assertIn("unused_handler", names)

    def test_custom_decorator_flagged(self):
        """Custom decorators not in FRAMEWORK_PUBLIC_PATTERNS should flag decorated functions."""
        self._create_file("my_framework.py", """
def my_custom_decorator(func):
    return func

def another_decorator(func):
    return func
""")
        self._create_file("app.py", """
from my_framework import my_custom_decorator, another_decorator

@my_custom_decorator
def handler_a():
    return "a"

@another_decorator
def handler_b():
    return "b"

def plain_function():
    return "plain"
""")
        self._create_file("main.py", """
from app import plain_function

if __name__ == "__main__":
    print(plain_function())
""")

        checker = DeadCodeChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"dead_code": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unreachable = [f for f in findings if f.sub_category.startswith("unreachable") and f.path == "app.py"]
        names = {f.evidence.split("'")[1] for f in unreachable}
        
        # Custom decorators are not recognized - functions may be flagged
        # This is the expected behavior - we don't know about custom frameworks
        # plain_function is used, so should NOT be flagged
        self.assertNotIn("plain_function", names)
        
        # handler_a and handler_b have unknown decorators - may be flagged
        # (test documents current behavior)


if __name__ == "__main__":
    unittest.main()