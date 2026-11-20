"""Check that two OpenAPI documents differ only in text (#478).

Compares paths, methods, operation ids, tags, parameters (name, location, required, schema), request bodies
and responses (status codes and schema references). ``summary``, ``description`` and the ``description``
of a parameter are ignored, so a wording change passes and anything structural fails. Parameters are compared as a set
keyed by (name, location): a reorder is not a difference. Component schemas are compared whole, descriptions included.

Usage::

    python -I scripts/compare_openapi_structure.py <base> <candidate>

Each argument is a path to an OpenAPI JSON file, or a git ref (``main``, ``origin/main``, a commit), which
is resolved to a commit and read as ``openapi.json`` from it. Prefix ``file:`` or ``ref:`` to say which is meant;
a bare argument is a file if one exists, else a ref. An argument beginning with ``-`` is refused. Exit status:
0 when the structures are equal, 1 when they are not (each difference is printed), 2 when an input cannot be read
or parsed (invalid JSON, no such file or ref, no git).
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List

_TEXT_KEYS = ("summary", "description")


def _fail(message: str) -> "SystemExit":
    """Build the exit for an unreadable input: one line on stderr, status 2 (1 means "differ").

    Parameters:
        message: The one-line reason.

    Returns:
        A ``SystemExit`` with status 2 to raise.
    """
    print(message, file=sys.stderr)
    return SystemExit(2)


def _git(*args: str) -> str:
    """Run git and return its stdout, or exit 2 with a one-line message.

    Parameters:
        *args: The git arguments.

    Returns:
        The command's stdout.

    Raises:
        SystemExit: With status 2 if git is missing or the command fails.
    """
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True)
    except OSError as error:
        raise _fail(f"cannot run git: {error}")
    if result.returncode != 0:
        raise _fail(f"git {args[0]} failed: {' '.join(result.stderr.split())[:200]}")
    return result.stdout


def load(source: str) -> Dict[str, Any]:
    """Read an OpenAPI document from a file path or a git ref.

    ``file:<path>`` and ``ref:<ref>`` say which one is meant. A bare argument is a file when one exists at that
    path, otherwise a ref. A ref is resolved to a commit (``git rev-parse --verify --end-of-options``) and
    read as ``<sha>:openapi.json``. An argument beginning with ``-`` is refused, so it can never be taken
    for an option.

    Parameters:
        source: ``file:<path>``, ``ref:<ref>``, or a bare path or ref.

    Returns:
        The parsed document.

    Raises:
        SystemExit: With status 2 if the source cannot be read or parsed.
    """
    if source.startswith("-"):
        raise _fail(f"refusing argument {source!r}: it begins with '-'")
    if source.startswith("file:"):
        kind, name = "file", source[len("file:") :]
    elif source.startswith("ref:"):
        kind, name = "ref", source[len("ref:") :]
    else:
        kind, name = ("file" if os.path.isfile(source) else "ref"), source
    if not name or name.startswith("-"):
        raise _fail(f"refusing argument {source!r}: empty, or begins with '-'")
    if kind == "file":
        try:
            with open(name, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError) as error:
            raise _fail(f"cannot read file {name!r}: {error}")
    else:
        sha = _git("rev-parse", "--verify", "--end-of-options", f"{name}^{{commit}}").strip()
        text = _git("show", f"{sha}:openapi.json")
    try:
        document = json.loads(text)
    except ValueError as error:
        raise _fail(f"{source!r} is not valid JSON: {error}")
    if not isinstance(document, dict):
        raise _fail(f"{source!r} is not an OpenAPI document (a JSON object)")
    return document


def _parameters_as_set(parameters: List[Any]) -> Any:
    """Key a parameter list by ``(name, in)`` so a reorder is not a difference.

    Parameters:
        parameters: The ``parameters`` array of an operation or path item.

    Returns:
        A dict keyed ``"<in>:<name>"``, or the list unchanged if an entry has no name and location (a ``$ref``).
    """
    keyed: Dict[str, Any] = {}
    for parameter in parameters:
        if not isinstance(parameter, dict) or "name" not in parameter or "in" not in parameter:
            return parameters
        keyed[f"{parameter['in']}:{parameter['name']}"] = parameter
    return keyed


def strip_text(node: Any, in_schema: bool = False) -> Any:
    """Return ``node`` without the wording a text-only change may touch.

    Drops ``summary`` and ``description`` from operations and parameters, and the top-level
    ``description`` of a parameter's or request body's schema (where FastAPI repeats the parameter text).
    Component schemas are kept whole, so a change to a model (including its field descriptions) counts as
    structural.

    Parameters:
        node: A JSON value from an operation or a path item.
        in_schema: Whether the walk is inside a schema, where ``description`` is kept.

    Returns:
        A copy with the text removed.
    """
    if isinstance(node, list):
        return [strip_text(item, in_schema) for item in node]
    if isinstance(node, dict) and not in_schema and isinstance(node.get("parameters"), list):
        node = {**node, "parameters": _parameters_as_set(node["parameters"])}
    if not isinstance(node, dict):
        return node
    out: Dict[str, Any] = {}
    for key, value in node.items():
        if key == "schema" and isinstance(value, dict) and not in_schema:
            # An inline parameter or body schema: its own description is the parameter / body text.
            out[key] = strip_text({k: v for k, v in value.items() if k != "description"}, True)
        elif key == "schemas":
            out[key] = strip_text(value, True)
        elif not in_schema and key in _TEXT_KEYS:
            continue
        else:
            out[key] = strip_text(value, in_schema)
    return out


def structure(document: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a document to what must not change under a text-only edit.

    Parameters:
        document: A parsed OpenAPI document.

    Returns:
        Paths with their methods, the components, and the rest of the document, without wording.
    """
    return {
        "paths": strip_text(document.get("paths", {})),
        "components": strip_text(document.get("components", {}), True),
        "servers": document.get("servers"),
        "openapi": document.get("openapi"),
    }


def diff(a: Any, b: Any, where: str = "") -> List[str]:
    """List the differences between two JSON values, with the path to each.

    Parameters:
        a: The base value.
        b: The candidate value.
        where: The path to the values, for the message.

    Returns:
        One line per difference.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        lines: List[str] = []
        for key in sorted(set(a) | set(b)):
            if key not in a:
                lines.append(f"added   {where}/{key}")
            elif key not in b:
                lines.append(f"removed {where}/{key}")
            else:
                lines += diff(a[key], b[key], f"{where}/{key}")
        return lines
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [line for index, (x, y) in enumerate(zip(a, b)) for line in diff(x, y, f"{where}[{index}]")]
    return [] if a == b else [f"changed {where}: {json.dumps(a)[:120]} -> {json.dumps(b)[:120]}"]


def main(argv: List[str]) -> int:
    """Compare two documents.

    Parameters:
        argv: ``[base, candidate]``.

    Returns:
        The exit status.
    """
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    differences = diff(structure(load(argv[0])), structure(load(argv[1])))
    for line in differences:
        print(line)
    if differences:
        print(f"{len(differences)} structural difference(s)")
        return 1
    print("openapi structure equal (text-only changes, if any)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
