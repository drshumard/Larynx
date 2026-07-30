"""
Backend regression + new-behavior tests for /app/backend/server.py after
extending seed + request-stitching to `eleven_v3`.

Uses the external REACT_APP_BACKEND_URL (APP_URL) with `/api` prefix.
Note: `GET /api/jobs/{id}` does NOT include the seed field — use
`GET /api/jobs/{id}/details` (which returns seed, tts_config,
regenerated_from, chunk_requests).
"""

import os
import sys
import time
import requests

BASE = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://c13eddd0-b7a5-4e2e-b9f4-46c909c653f2.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"

# Realistic long-form sample (~1600+ chars) - Herman Melville-esque passage
SAMPLE_TEXT = (
    "Call me Ishmael. Some years ago—never mind how long precisely—having "
    "little or no money in my purse, and nothing particular to interest me "
    "on shore, I thought I would sail about a little and see the watery "
    "part of the world. It is a way I have of driving off the spleen and "
    "regulating the circulation. Whenever I find myself growing grim about "
    "the mouth; whenever it is a damp, drizzly November in my soul; "
    "whenever I find myself involuntarily pausing before coffin warehouses, "
    "and bringing up the rear of every funeral I meet; and especially "
    "whenever my hypos get such an upper hand of me, that it requires a "
    "strong moral principle to prevent me from deliberately stepping into "
    "the street, and methodically knocking people's hats off—then, I "
    "account it high time to get to sea as soon as I can. This is my "
    "substitute for pistol and ball. With a philosophical flourish Cato "
    "throws himself upon his sword; I quietly take to the ship. There is "
    "nothing surprising in this. If they but knew it, almost all men in "
    "their degree, some time or other, cherish very nearly the same "
    "feelings towards the ocean with me. There now is your insular city of "
    "the Manhattoes, belted round by wharves as Indian isles by coral "
    "reefs—commerce surrounds it with her surf. Right and left, the streets "
    "take you waterward. Its extreme downtown is the battery, where that "
    "noble mole is washed by waves, and cooled by breezes, which a few "
    "hours previous were out of sight of land. Look at the crowds of "
    "water-gazers there. Circumambulate the city of a dreamy Sabbath "
    "afternoon. Go from Corlears Hook to Coenties Slip, and from thence, "
    "by Whitehall, northward. What do you see?"
)

created_job_ids: list = []
results = {}  # test_name -> (pass_bool, evidence_str)


def record(name, ok, evidence=""):
    results[name] = (ok, evidence)
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}: {evidence}")


def _put_settings(patch: dict):
    """Merge patch into current settings and PUT full body."""
    cur = requests.get(f"{API}/settings", timeout=15).json()
    cur.pop("_id", None)
    cur.update(patch)
    r = requests.put(f"{API}/settings", json=cur, timeout=20)
    r.raise_for_status()
    return r.json()


def _create_job(name: str):
    payload = {"name": name, "text": SAMPLE_TEXT}
    r = requests.post(f"{API}/jobs", json=payload, timeout=30)
    r.raise_for_status()
    j = r.json()
    jid = j["id"]
    created_job_ids.append(jid)
    return jid


def _get_details(job_id: str):
    r = requests.get(f"{API}/jobs/{job_id}/details", timeout=15)
    r.raise_for_status()
    return r.json()


# 1. OpenAPI reachable
def test_openapi():
    try:
        r = requests.get(f"{API}/openapi.json", timeout=15)
        ok_status = r.status_code == 200
        data = r.json()
        has_paths = "/api/jobs" in (data.get("paths") or {})
        ok = ok_status and has_paths
        record(
            "openapi_reachable",
            ok,
            f"status={r.status_code}, /api/jobs in paths={has_paths}",
        )
    except Exception as e:
        record("openapi_reachable", False, f"exception: {e}")


# 2. Health
def test_health():
    try:
        r = requests.get(f"{API}/health", timeout=15)
        data = r.json()
        ok = r.status_code == 200 and data.get("status") == "healthy"
        record("health", ok, f"status={r.status_code} body={data}")
    except Exception as e:
        record("health", False, f"exception: {e}")


# 3. v3 seed generation
def test_v3_seed():
    try:
        _put_settings({"mode": "chunking", "model_id": "eleven_v3", "chunk_size": 4500})
        jid = _create_job("v3 seed test")
        time.sleep(0.3)
        det = _get_details(jid)
        seed = det.get("seed")
        model_id = (det.get("tts_config") or {}).get("model_id")
        chunk_count = det.get("chunk_count", 0)
        ok = (
            isinstance(seed, int)
            and 0 <= seed <= 2**31 - 1
            and model_id == "eleven_v3"
            and chunk_count >= 1
        )
        record(
            "v3_seed_generated",
            ok,
            f"job_id={jid} seed={seed} model={model_id} chunks={chunk_count}",
        )
        return jid
    except Exception as e:
        record("v3_seed_generated", False, f"exception: {e}")
        return None


# 4. turbo -> seed null
def test_turbo_seed_null():
    try:
        _put_settings({"mode": "chunking", "model_id": "eleven_turbo_v2_5"})
        jid = _create_job("turbo seed null test")
        time.sleep(0.3)
        det = _get_details(jid)
        seed = det.get("seed")
        model_id = (det.get("tts_config") or {}).get("model_id")
        ok = seed is None and model_id == "eleven_turbo_v2_5"
        record(
            "turbo_seed_null",
            ok,
            f"job_id={jid} seed={seed} model={model_id}",
        )
    except Exception as e:
        record("turbo_seed_null", False, f"exception: {e}")


# 5. studio mode -> seed null even with v3 model
def test_studio_seed_null():
    try:
        _put_settings({"mode": "studio", "model_id": "eleven_v3"})
        jid = _create_job("studio v3 seed null test")
        time.sleep(0.3)
        det = _get_details(jid)
        seed = det.get("seed")
        cfg = det.get("tts_config") or {}
        ok = (
            seed is None
            and cfg.get("mode") == "studio"
            and cfg.get("model_id") == "eleven_v3"
        )
        record(
            "studio_seed_null",
            ok,
            f"job_id={jid} seed={seed} mode={cfg.get('mode')} model={cfg.get('model_id')}",
        )
    except Exception as e:
        record("studio_seed_null", False, f"exception: {e}")
    finally:
        try:
            _put_settings({"mode": "chunking"})
        except Exception:
            pass


# 6. v2 unchanged
def test_v2_seed():
    try:
        _put_settings({"mode": "chunking", "model_id": "eleven_multilingual_v2", "chunk_size": 4500})
        jid = _create_job("v2 seed test")
        time.sleep(0.3)
        det = _get_details(jid)
        seed = det.get("seed")
        model_id = (det.get("tts_config") or {}).get("model_id")
        ok = (
            isinstance(seed, int)
            and 0 <= seed <= 2**31 - 1
            and model_id == "eleven_multilingual_v2"
        )
        record(
            "v2_seed_generated",
            ok,
            f"job_id={jid} seed={seed} model={model_id}",
        )
        return jid
    except Exception as e:
        record("v2_seed_generated", False, f"exception: {e}")
        return None


# 7 & 8. Regenerate reuses seed
def test_regenerate_reuses_seed(src_job_id, label, expected_model):
    if not src_job_id:
        record(f"regenerate_reuses_seed_{label}", False, "no source job id")
        return
    try:
        src_det = _get_details(src_job_id)
        src_seed = src_det.get("seed")

        r = requests.post(f"{API}/jobs/{src_job_id}/regenerate", timeout=30)
        if r.status_code != 200:
            record(
                f"regenerate_reuses_seed_{label}",
                False,
                f"regenerate returned {r.status_code}: {r.text[:200]}",
            )
            return
        new_jid = r.json()["id"]
        created_job_ids.append(new_jid)
        time.sleep(0.3)

        new_det = _get_details(new_jid)
        new_seed = new_det.get("seed")
        new_model = (new_det.get("tts_config") or {}).get("model_id")
        regenerated_from = new_det.get("regenerated_from")

        ok = (
            isinstance(new_seed, int)
            and new_seed == src_seed
            and regenerated_from == src_job_id
            and new_model == expected_model
        )
        record(
            f"regenerate_reuses_seed_{label}",
            ok,
            f"src={src_job_id} src_seed={src_seed} new_job={new_jid} new_seed={new_seed} "
            f"model={new_model} regenerated_from={regenerated_from}",
        )
    except Exception as e:
        record(f"regenerate_reuses_seed_{label}", False, f"exception: {e}")


# 9. Cleanup
def cleanup():
    ok_all = True
    per = []
    for jid in list(created_job_ids):
        try:
            r = requests.delete(f"{API}/jobs/{jid}", timeout=15)
            per.append(f"{jid}={r.status_code}")
            if r.status_code not in (200, 204):
                ok_all = False
        except Exception as e:
            per.append(f"{jid}=ERR({e})")
            ok_all = False
    record("cleanup", ok_all, "; ".join(per) if per else "no jobs to delete")


def main():
    print(f"Base API: {API}")
    test_openapi()
    test_health()

    v3_jid = test_v3_seed()
    test_turbo_seed_null()
    test_studio_seed_null()
    v2_jid = test_v2_seed()

    test_regenerate_reuses_seed(v3_jid, "v3", "eleven_v3")
    test_regenerate_reuses_seed(v2_jid, "v2", "eleven_multilingual_v2")

    cleanup()

    print("\n===== SUMMARY =====")
    total = len(results)
    passed = sum(1 for ok, _ in results.values() if ok)
    for name, (ok, ev) in results.items():
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}: {ev}")
    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
