from core.services import process_data
from core.handlers import app
from inheritance.derived import DerivedClass
from nested.funcs import outer_a, outer_b
from legacy.old_api import normalize as legacy_normalize
from utils.string_helpers import normalize

if __name__ == "__main__":
    # Entry point - makes core.services reachable
    result = process_data("  hello world  ")
    print(f"Processed: {result}")
    
    # Use derived class
    d = DerivedClass()
    print(f"Derived: {d.process()}")
    
    # Nested functions
    print(f"Outer A: {outer_a()}")
    print(f"Outer B: {outer_b()}")
    
    # Legacy duplicate
    print(f"Legacy: {legacy_normalize('  test  ')}")
    print(f"Utils: {normalize('  test  ')}")
    
    # Framework handlers are reachable via app
    print("App routes registered")