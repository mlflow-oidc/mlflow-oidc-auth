from flask import Response, jsonify, make_response


def make_auth_required_response() -> Response:
    response = make_response(jsonify({"message": "Authentication required"}))
    response.status_code = 401
    return response


def make_forbidden_response(msg={"message": "Permission denied"}) -> Response:
    response = make_response(jsonify(msg))
    response.status_code = 403
    return response


def make_basic_auth_response() -> Response:
    response = make_response(
        "You are not authenticated. Please see documentation for details" "https://github.com/mlflow-oidc/mlflow-oidc-auth"
    )
    response.status_code = 401
    response.headers["WWW-Authenticate"] = 'Basic realm="mlflow"'
    return response
