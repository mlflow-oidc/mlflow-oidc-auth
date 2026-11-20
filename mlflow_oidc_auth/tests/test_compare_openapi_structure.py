"""Unit tests for scripts/compare_openapi_structure.py (#478)."""

import copy
import importlib.util
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "compare_openapi_structure.py"
_spec = importlib.util.spec_from_file_location("compare_openapi_structure", _SCRIPT)
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)

BASE = {
    "openapi": "3.1.0",
    "paths": {
        "/things/{id}": {
            "get": {
                "operationId": "get_thing",
                "summary": "Get a thing",
                "description": "Gets one thing.",
                "tags": ["things"],
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "description": "The id", "schema": {"type": "string", "description": "The id"}},
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}},
                },
            }
        }
    },
    "components": {
        "schemas": {"Thing": {"type": "object", "description": "A thing", "properties": {"description": {"type": "string", "description": "Text"}}}}
    },
}


def _changed(mutate):
    doc = copy.deepcopy(BASE)
    mutate(doc)
    return compare.diff(compare.structure(BASE), compare.structure(doc))


def _op(doc):
    return doc["paths"]["/things/{id}"]["get"]


def test_identical_documents_are_equal():
    assert _changed(lambda d: None) == []


def test_text_only_changes_are_equal():
    def mutate(doc):
        op = _op(doc)
        op["summary"], op["description"] = "New summary", "New description"
        op["parameters"][0]["description"] = "Other"
        op["parameters"][0]["schema"]["description"] = "Other"
        op["responses"]["200"]["description"] = "Fine"

    assert _changed(mutate) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: _op(d).__setitem__("operationId", "get_thing_2"),
        lambda d: d["paths"].__setitem__("/other/{id}", d["paths"].pop("/things/{id}")),
        lambda d: d["paths"]["/things/{id}"].__setitem__("post", d["paths"]["/things/{id}"].pop("get")),
        lambda d: _op(d)["responses"].__setitem__("201", _op(d)["responses"].pop("200")),
        lambda d: _op(d)["responses"]["200"]["content"]["application/json"]["schema"].__setitem__("$ref", "#/components/schemas/Other"),
        lambda d: _op(d)["parameters"][1].__setitem__("name", "page"),
        lambda d: _op(d)["parameters"][1].__setitem__("in", "header"),
        lambda d: _op(d)["parameters"][1].__setitem__("required", True),
        lambda d: _op(d)["parameters"].pop(),
        lambda d: _op(d).__setitem__("tags", ["other"]),
    ],
    ids=["operation-id", "path", "method", "status", "schema-ref", "parameter-name", "parameter-location", "parameter-required", "parameter-removed", "tags"],
)
def test_structural_changes_differ(mutate):
    assert _changed(mutate) != []


def test_parameter_reorder_is_equal():
    assert _changed(lambda d: _op(d)["parameters"].reverse()) == []


def test_parameters_are_keyed_by_name_and_location():
    def mutate(doc):
        _op(doc)["parameters"].append({"name": "limit", "in": "header", "schema": {"type": "integer"}})

    assert _changed(mutate) != []


def test_description_is_ignored_only_outside_schemas():
    # A component schema's own description and its properties are structural.
    assert _changed(lambda d: d["components"]["schemas"]["Thing"].__setitem__("description", "changed")) != []
    assert _changed(lambda d: d["components"]["schemas"]["Thing"]["properties"]["description"].__setitem__("description", "changed")) != []
    # A property that is literally named "description" inside an inline schema survives the strip.
    doc = copy.deepcopy(BASE)
    _op(doc)["parameters"][1]["schema"] = {"type": "object", "properties": {"description": {"type": "string"}}}
    other = copy.deepcopy(doc)
    other["paths"]["/things/{id}"]["get"]["parameters"][1]["schema"]["properties"]["description"]["type"] = "integer"
    assert compare.diff(compare.structure(doc), compare.structure(other)) != []
    removed = copy.deepcopy(doc)
    del removed["paths"]["/things/{id}"]["get"]["parameters"][1]["schema"]["properties"]["description"]
    assert compare.diff(compare.structure(doc), compare.structure(removed)) != []


def test_main_exit_codes(tmp_path):
    import json

    a, b, c = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
    a.write_text(json.dumps(BASE))
    reworded = copy.deepcopy(BASE)
    _op(reworded)["summary"] = "x"
    b.write_text(json.dumps(reworded))
    structural = copy.deepcopy(BASE)
    _op(structural)["operationId"] = "x"
    c.write_text(json.dumps(structural))
    assert compare.main([str(a), str(b)]) == 0
    assert compare.main([str(a), str(c)]) == 1
    assert compare.main([str(a)]) == 2


def _write(path, document):
    import json

    path.write_text(json.dumps(document))
    return str(path)


def test_unreadable_inputs_exit_2_not_1(tmp_path, capsys):
    """Exit 1 means "differ"; an input that cannot be read or parsed is 2, with a one-line message."""
    good = _write(tmp_path / "good.json", BASE)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    array = _write(tmp_path / "array.json", [])
    for source in (str(bad), array, "file:" + str(tmp_path / "missing.json")):
        with pytest.raises(SystemExit) as raised:
            compare.main([good, source])
        assert raised.value.code == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 3 and all(line for line in err)


def test_missing_git_binary_exits_2(monkeypatch, tmp_path):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(compare.subprocess, "run", no_git)
    with pytest.raises(SystemExit) as raised:
        compare.load("ref:main")
    assert raised.value.code == 2


@pytest.mark.parametrize("source", ["-p", "--output=x", "file:-x", "ref:--upload-pack=x", "ref:", "file:"])
def test_arguments_beginning_with_a_dash_are_refused(source, capsys):
    with pytest.raises(SystemExit) as raised:
        compare.load(source)
    assert raised.value.code == 2
    assert "refusing" in capsys.readouterr().err


def test_refs_resolve_to_a_commit_and_prefixes_disambiguate(tmp_path, monkeypatch):
    import json
    import subprocess

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "openapi.json").write_text(json.dumps(BASE))
    git("add", "openapi.json")
    git("commit", "-q", "-m", "base")
    git("tag", "v1")
    changed = copy.deepcopy(BASE)
    _op(changed)["operationId"] = "x"
    # A file named like the ref shadows it for a bare argument, but not for "ref:".
    (tmp_path / "v1").write_text(json.dumps(changed))
    monkeypatch.chdir(tmp_path)
    assert compare.load("v1") == changed
    assert compare.load("file:v1") == changed
    assert compare.load("ref:v1") == BASE
    assert compare.load("ref:HEAD") == BASE
    with pytest.raises(SystemExit) as raised:
        compare.load("ref:no-such-ref")
    assert raised.value.code == 2
