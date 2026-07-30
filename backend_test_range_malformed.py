"""
Retest: malformed Range header should fall back to 200 (RFC 7233 §3.1).
Seeded job (do NOT delete): 6a6b6ec9879fe7e7aac047a2
"""
import os
import sys
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or \
    "https://c13eddd0-b7a5-4e2e-b9f4-46c909c653f2.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

JOB_ID = "6a6b6ec9879fe7e7aac047a2"
FULL_URL = f"{API}/jobs/{JOB_ID}/download"
CHUNK0_URL = f"{API}/jobs/{JOB_ID}/chunks/0/audio"

FULL_SIZE = 721022
CHUNK0_SIZE = 353218

results = []


def _check(name, cond, detail):
    tag = "PASS" if cond else "FAIL"
    results.append((tag, name, detail))
    print(f"[{tag}] {name}")
    for k, v in detail.items():
        print(f"       {k}: {v}")


def read_body_len(resp):
    n = 0
    for chunk in resp.iter_content(chunk_size=65536):
        n += len(chunk)
    return n


# ---------------------------------------------------------------------------
# 1. Range: potato → 200 + Accept-Ranges + full body
# ---------------------------------------------------------------------------
r = requests.get(FULL_URL, headers={"Range": "potato"}, stream=True, timeout=30)
body_len = read_body_len(r)
_check(
    "1. Range: potato -> 200 full body",
    r.status_code == 200
    and r.headers.get("Accept-Ranges") == "bytes"
    and r.headers.get("Content-Length") == str(FULL_SIZE)
    and body_len == FULL_SIZE
    and "Content-Range" not in r.headers,
    {
        "status": r.status_code,
        "Accept-Ranges": r.headers.get("Accept-Ranges"),
        "Content-Length": r.headers.get("Content-Length"),
        "Content-Range": r.headers.get("Content-Range"),
        "body_len": body_len,
    },
)

# ---------------------------------------------------------------------------
# 2a. Range: bytes=100-200 → 206 + Content-Range + 101 bytes
# ---------------------------------------------------------------------------
r = requests.get(FULL_URL, headers={"Range": "bytes=100-200"}, stream=True, timeout=30)
body_len = read_body_len(r)
_check(
    "2a. Range: bytes=100-200 -> 206 partial",
    r.status_code == 206
    and r.headers.get("Content-Range") == f"bytes 100-200/{FULL_SIZE}"
    and body_len == 101,
    {
        "status": r.status_code,
        "Content-Range": r.headers.get("Content-Range"),
        "Content-Length": r.headers.get("Content-Length"),
        "body_len": body_len,
    },
)

# ---------------------------------------------------------------------------
# 2b. Chunk 0 with Range: bytes=99999999- → 416 with Content-Range: */353218
# ---------------------------------------------------------------------------
r = requests.get(CHUNK0_URL, headers={"Range": "bytes=99999999-"}, stream=True, timeout=30)
body_len = read_body_len(r)
_check(
    "2b. Chunk0 Range: bytes=99999999- -> 416",
    r.status_code == 416
    and r.headers.get("Content-Range") == f"bytes */{CHUNK0_SIZE}",
    {
        "status": r.status_code,
        "Content-Range": r.headers.get("Content-Range"),
        "body_len": body_len,
    },
)

# ---------------------------------------------------------------------------
# 3. Range: pages=0-100 → 200 + full body
# ---------------------------------------------------------------------------
r = requests.get(FULL_URL, headers={"Range": "pages=0-100"}, stream=True, timeout=30)
body_len = read_body_len(r)
_check(
    "3. Range: pages=0-100 -> 200 full body",
    r.status_code == 200
    and r.headers.get("Accept-Ranges") == "bytes"
    and r.headers.get("Content-Length") == str(FULL_SIZE)
    and body_len == FULL_SIZE
    and "Content-Range" not in r.headers,
    {
        "status": r.status_code,
        "Accept-Ranges": r.headers.get("Accept-Ranges"),
        "Content-Length": r.headers.get("Content-Length"),
        "Content-Range": r.headers.get("Content-Range"),
        "body_len": body_len,
    },
)

# ---------------------------------------------------------------------------
# 4. Range: (whitespace only / empty) → 200 + full body
# `requests` refuses to send whitespace-only header values, so use a raw
# http.client connection which will happily transmit `Range:  \r\n`.
# ---------------------------------------------------------------------------
import http.client
from urllib.parse import urlparse

parsed = urlparse(FULL_URL)
conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
conn = conn_cls(parsed.netloc, timeout=30)
conn.putrequest("GET", parsed.path + (("?" + parsed.query) if parsed.query else ""))
conn.putheader("Host", parsed.netloc)
conn.putheader("Accept", "*/*")
conn.putheader("Range", " ")  # whitespace-only value
conn.endheaders()
resp = conn.getresponse()
status = resp.status
raw_headers = {k: v for k, v in resp.getheaders()}
body_bytes = resp.read()
body_len = len(body_bytes)
conn.close()

# Case-insensitive lookup helper
def _hget(d, k):
    for kk, vv in d.items():
        if kk.lower() == k.lower():
            return vv
    return None

_check(
    "4. Range: '<space>' (whitespace) -> 200 full body",
    status == 200
    and _hget(raw_headers, "Accept-Ranges") == "bytes"
    and _hget(raw_headers, "Content-Length") == str(FULL_SIZE)
    and body_len == FULL_SIZE
    and _hget(raw_headers, "Content-Range") is None,
    {
        "status": status,
        "Accept-Ranges": _hget(raw_headers, "Accept-Ranges"),
        "Content-Length": _hget(raw_headers, "Content-Length"),
        "Content-Range": _hget(raw_headers, "Content-Range"),
        "body_len": body_len,
    },
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
n_pass = sum(1 for t, _, _ in results if t == "PASS")
n_fail = sum(1 for t, _, _ in results if t == "FAIL")
print(f"RESULT: {n_pass} PASS, {n_fail} FAIL, out of {len(results)}")
for tag, name, _ in results:
    print(f"  [{tag}] {name}")

sys.exit(0 if n_fail == 0 else 1)
