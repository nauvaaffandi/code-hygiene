"""Derived class overriding process and calling super()."""

from .base import BaseClass


class DerivedClass(BaseClass):
    def process(self):
        """Override process and call super()."""
        base_result = super().process()
        return f"derived -> {base_result}"

    def derived_only(self):
        """Method only in derived class."""
        return "derived only"

    def unused_derived_method(self):
        """Unused method in derived class."""
        return "unused derived"