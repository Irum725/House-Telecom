"""Synchronous WSGI adapter for hosting FastAPI on PythonAnywhere and uWSGI without thread deadlocks."""

import io
from fastapi.testclient import TestClient
from backend.app.main import app

# TestClient runs FastAPI in-process synchronously without spawning background worker threads
_client = TestClient(app, raise_server_exceptions=False)


def application(environ, start_response):
    """Standard WSGI entrypoint callable by uWSGI."""
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    url = path + (f"?{query}" if query else "")
    method = environ.get("REQUEST_METHOD", "GET")

    headers = {
        k[5:].replace("_", "-").lower(): v
        for k, v in environ.items()
        if k.startswith("HTTP_")
    }
    if "CONTENT_TYPE" in environ and environ["CONTENT_TYPE"]:
        headers["content-type"] = environ["CONTENT_TYPE"]

    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        content_length = 0

    body = environ["wsgi.input"].read(content_length) if content_length > 0 else None

    resp = _client.request(method=method, url=url, headers=headers, content=body)

    status_phrase = "OK" if resp.status_code == 200 else ""
    status_str = f"{resp.status_code} {status_phrase}".strip()
    response_headers = [(k, v) for k, v in resp.headers.items() if k.lower() != "content-length"]
    response_headers.append(("Content-Length", str(len(resp.content))))

    start_response(status_str, response_headers)
    return [resp.content]


# Alias for compatibility
wsgi_app = application
