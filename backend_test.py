"""
Backend tests for HTTP Range support on audio endpoints (scrub bug fix).

Covers:
- /api/jobs/{id}/download          (main audio)
- /api/jobs/{id}/chunks/{i}/audio  (chunk audio)

Regression:
- /api/health
- /api/jobs/{id}/details
- /api/openapi.json
"""
import hashlib
import os
import sys
import requests

# Base URL — prefer external, fallback to internal.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    BASE_URL = "https://c13eddd0-b7a5-4e2e-b9f4-46c909c653f2.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

JOB_ID = "6a6b6ec9879fe7e7aac047a2"
DOWNLOAD_URL = f"{API}/jobs/{JOB_ID}/download"
CHUNK0_URL = f"{API}/jobs/{JOB_ID}/chunks/0/audio"
CHUNK1_URL = f"{API}/jobs/{JOB_ID}/chunks/1/audio"

FULL_SIZE = 721022
CHUNK0_SIZE = 353218
CHUNK1_SIZE = 369101

results = []


def rec(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append((name, ok, detail))


def hdr(h, key):
    return h.get(key)


def read_body_len(resp):
    return len(resp.content)


def test_1_no_range():
    r = requests.get(DOWNLOAD_URL, timeout=30)
    detail = f"status={r.status_code} CL={hdr(r.headers,'Content-Length')} AR={hdr(r.headers,'Accept-Ranges')} CD={hdr(r.headers,'Content-Disposition')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 200
        and hdr(r.headers, "Accept-Ranges") == "bytes"
        and hdr(r.headers, "Content-Length") == str(FULL_SIZE)
        and (hdr(r.headers, "Content-Disposition") or "").lower().startswith("attachment")
        and read_body_len(r) == FULL_SIZE
    )
    rec("1. download GET no-Range 200/full", ok, detail)


def test_2_range_100_200():
    r = requests.get(DOWNLOAD_URL, headers={"Range": "bytes=100-200"}, timeout=30)
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')} CL={hdr(r.headers,'Content-Length')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 206
        and hdr(r.headers, "Content-Range") == f"bytes 100-200/{FULL_SIZE}"
        and hdr(r.headers, "Content-Length") == "101"
        and read_body_len(r) == 101
    )
    rec("2. download Range: bytes=100-200 -> 206", ok, detail)


def test_3_range_500000_open():
    r = requests.get(DOWNLOAD_URL, headers={"Range": "bytes=500000-"}, timeout=30)
    exp_cr = f"bytes 500000-{FULL_SIZE - 1}/{FULL_SIZE}"
    exp_len = FULL_SIZE - 500000
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')} CL={hdr(r.headers,'Content-Length')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 206
        and hdr(r.headers, "Content-Range") == exp_cr
        and hdr(r.headers, "Content-Length") == str(exp_len)
        and read_body_len(r) == exp_len
    )
    rec("3. download Range: bytes=500000- -> 206", ok, detail)


def test_4_suffix_range():
    r = requests.get(DOWNLOAD_URL, headers={"Range": "bytes=-1024"}, timeout=30)
    exp_cr = f"bytes {FULL_SIZE - 1024}-{FULL_SIZE - 1}/{FULL_SIZE}"
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')} CL={hdr(r.headers,'Content-Length')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 206
        and hdr(r.headers, "Content-Range") == exp_cr
        and hdr(r.headers, "Content-Length") == "1024"
        and read_body_len(r) == 1024
    )
    rec("4. download suffix Range: bytes=-1024 -> 206", ok, detail)


def test_5_unsatisfiable():
    r = requests.get(DOWNLOAD_URL, headers={"Range": "bytes=99999999-"}, timeout=30)
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')}"
    ok = r.status_code == 416 and hdr(r.headers, "Content-Range") == f"bytes */{FULL_SIZE}"
    rec("5. download unsatisfiable Range -> 416", ok, detail)


def test_6_malformed():
    r = requests.get(DOWNLOAD_URL, headers={"Range": "potato"}, timeout=30)
    detail = f"status={r.status_code} AR={hdr(r.headers,'Accept-Ranges')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 200
        and hdr(r.headers, "Accept-Ranges") == "bytes"
        and read_body_len(r) == FULL_SIZE
    )
    rec("6. download malformed Range -> 200 fallback", ok, detail)


def test_7_chunk_no_range():
    r = requests.get(CHUNK0_URL, timeout=30)
    detail = f"status={r.status_code} CL={hdr(r.headers,'Content-Length')} AR={hdr(r.headers,'Accept-Ranges')} CD={hdr(r.headers,'Content-Disposition')} body_len={read_body_len(r)}"
    cd = (hdr(r.headers, "Content-Disposition") or "").lower()
    ok = (
        r.status_code == 200
        and hdr(r.headers, "Content-Length") == str(CHUNK0_SIZE)
        and hdr(r.headers, "Accept-Ranges") == "bytes"
        and cd.startswith("inline")
        and read_body_len(r) == CHUNK0_SIZE
    )
    rec("7. chunk0 GET no-Range 200/inline", ok, detail)


def test_8_chunk_range():
    r = requests.get(CHUNK0_URL, headers={"Range": "bytes=1000-2000"}, timeout=30)
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')} CL={hdr(r.headers,'Content-Length')} body_len={read_body_len(r)}"
    ok = (
        r.status_code == 206
        and hdr(r.headers, "Content-Range") == f"bytes 1000-2000/{CHUNK0_SIZE}"
        and hdr(r.headers, "Content-Length") == "1001"
        and read_body_len(r) == 1001
    )
    rec("8. chunk0 Range: bytes=1000-2000 -> 206", ok, detail)


def test_9_byte_integrity():
    r_full = requests.get(CHUNK0_URL, timeout=30)
    if r_full.status_code != 200 or len(r_full.content) != CHUNK0_SIZE:
        rec("9. chunk0 byte-integrity md5 concat==full", False,
            f"full fetch bad: status={r_full.status_code} len={len(r_full.content)}")
        return
    full_md5 = hashlib.md5(r_full.content).hexdigest()

    r_a = requests.get(CHUNK0_URL, headers={"Range": "bytes=0-176608"}, timeout=30)
    r_b = requests.get(CHUNK0_URL, headers={"Range": "bytes=176609-353217"}, timeout=30)
    if r_a.status_code != 206 or r_b.status_code != 206:
        rec("9. chunk0 byte-integrity md5 concat==full", False,
            f"range statuses a={r_a.status_code} b={r_b.status_code}")
        return
    concat = r_a.content + r_b.content
    concat_md5 = hashlib.md5(concat).hexdigest()
    ok = (
        len(r_a.content) == 176609
        and len(r_b.content) == 176609
        and len(concat) == CHUNK0_SIZE
        and concat_md5 == full_md5
    )
    detail = f"a_len={len(r_a.content)} b_len={len(r_b.content)} concat_len={len(concat)} full_md5={full_md5[:8]} concat_md5={concat_md5[:8]}"
    rec("9. chunk0 byte-integrity md5 concat==full", ok, detail)


def test_10_chunk_unsatisfiable():
    r = requests.get(CHUNK0_URL, headers={"Range": "bytes=99999999-"}, timeout=30)
    detail = f"status={r.status_code} CR={hdr(r.headers,'Content-Range')}"
    ok = r.status_code == 416 and hdr(r.headers, "Content-Range") == f"bytes */{CHUNK0_SIZE}"
    rec("10. chunk0 unsatisfiable Range -> 416", ok, detail)


def test_11_health():
    r = requests.get(f"{API}/health", timeout=15)
    try:
        body = r.json()
    except Exception:
        body = {}
    ok = r.status_code == 200 and body.get("status") == "healthy"
    rec("11. /api/health -> 200 healthy", ok, f"status={r.status_code} body={r.text[:80]}")


def test_12_job_details():
    r = requests.get(f"{API}/jobs/{JOB_ID}/details", timeout=15)
    try:
        j = r.json()
    except Exception:
        j = {}
    seed = j.get("seed")
    tts = j.get("tts_config", {}) or {}
    model = tts.get("model_id")
    status = j.get("status")
    ok = (
        r.status_code == 200
        and seed == 424242
        and model == "eleven_v3"
        and status == "completed"
    )
    rec("12. job details seeded (seed=424242, model=eleven_v3, completed)", ok,
        f"status={r.status_code} seed={seed} model={model} job_status={status}")


def test_13_openapi():
    r = requests.get(f"{API}/openapi.json", timeout=15)
    ok = r.status_code == 200 and "openapi" in r.text[:200]
    rec("13. /api/openapi.json -> 200", ok, f"status={r.status_code}")


def main():
    print(f"Base API: {API}")
    print(f"Job ID:   {JOB_ID}")
    print("=" * 70)

    tests = [
        test_1_no_range, test_2_range_100_200, test_3_range_500000_open,
        test_4_suffix_range, test_5_unsatisfiable, test_6_malformed,
        test_7_chunk_no_range, test_8_chunk_range, test_9_byte_integrity,
        test_10_chunk_unsatisfiable,
        test_11_health, test_12_job_details, test_13_openapi,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            rec(t.__name__, False, f"EXCEPTION: {type(e).__name__}: {e}")

    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"TOTAL: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
