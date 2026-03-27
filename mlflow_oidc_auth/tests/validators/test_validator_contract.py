"""Contract enforcement tests for all validate_can_* functions.

Ensures every validator function in the validators package:
1. Has an explicit ``-> bool`` return type annotation.
2. Accepts exactly one positional parameter (username: str).

This prevents the return-type mismatch bug where workspace validators
returned ``None``/``Response`` instead of ``bool``, causing the
``if not validator(username)`` check in ``before_request_hook`` to
incorrectly deny all non-admin workspace requests.
"""

import inspect
import importlib
import pkgutil

import pytest

import mlflow_oidc_auth.validators as validators_pkg


def _discover_validate_functions():
    """Discover all ``validate_can_*`` functions across the validators package.

    Returns a list of (qualified_name, function) tuples.
    """
    results = []

    for importer, modname, ispkg in pkgutil.walk_packages(
        validators_pkg.__path__,
        prefix=validators_pkg.__name__ + ".",
    ):
        module = importlib.import_module(modname)
        for attr_name in dir(module):
            if not attr_name.startswith("validate_can_"):
                continue
            obj = getattr(module, attr_name)
            if callable(obj) and inspect.isfunction(obj):
                qualified = f"{modname}.{attr_name}"
                results.append((qualified, obj))

    # Deduplicate (re-exports from __init__.py share identity)
    seen = set()
    unique = []
    for qname, fn in results:
        if id(fn) not in seen:
            seen.add(id(fn))
            unique.append((qname, fn))
    return unique


_VALIDATORS = _discover_validate_functions()


class TestValidatorReturnTypeAnnotation:
    """Every validate_can_* function MUST declare ``-> bool``."""

    @pytest.mark.parametrize(
        "qualified_name,fn",
        _VALIDATORS,
        ids=[qn for qn, _ in _VALIDATORS],
    )
    def test_return_annotation_is_bool(self, qualified_name, fn):
        """Validator {qualified_name} must have -> bool annotation."""
        hints = inspect.get_annotations(fn, eval_str=True)
        assert "return" in hints, f"{qualified_name} is missing a return type annotation. " f"All validators must declare -> bool."
        assert hints["return"] is bool, (
            f"{qualified_name} has return annotation {hints['return']!r}, expected bool. " f"Validators must return True (allowed) or False (denied)."
        )


class TestValidatorSignature:
    """Every validate_can_* function MUST accept a single ``username`` parameter."""

    @pytest.mark.parametrize(
        "qualified_name,fn",
        _VALIDATORS,
        ids=[qn for qn, _ in _VALIDATORS],
    )
    def test_accepts_username_parameter(self, qualified_name, fn):
        """Validator {qualified_name} must accept (username: str) as its only param."""
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        assert len(params) >= 1, f"{qualified_name} has no parameters; expected at least (username: str)."
        first = params[0]
        assert first.name == "username", f"{qualified_name} first parameter is '{first.name}', expected 'username'."


class TestValidatorDiscovery:
    """Sanity check: we actually found a reasonable number of validators."""

    def test_minimum_validator_count(self):
        """Should discover at least 50 validate_can_* functions."""
        assert len(_VALIDATORS) >= 50, f"Only found {len(_VALIDATORS)} validators; expected >= 50. " f"Discovery may be broken."
