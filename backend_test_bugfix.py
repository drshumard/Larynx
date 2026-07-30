"""
Backend BUG-FIX verification tests for the seed / previous_request_ids split.

Bug: v3 chunk calls were sent with previous_request_ids and rejected by
ElevenLabs with HTTP 400 unsupported_model. Fix separated:
  SEED_MODELS = {eleven_multilingual_v2, eleven_v3}
  STITCHING_MODELS = {eleven_multilingual_v2}
so `previous_request_ids` is only sent for multilingual_v2.

Covers:
  A) Regression: creation-time seed guards (v3/v2/turbo/studio + regenerate).
  B) chunk_requests[i] shape after live TTS run.
  C) Backend log sanity for "unsupported_model" / "previous_request_ids".
"""

import os
import sys
import time
import subprocess
import requests

BASE = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://c13eddd0-b7a5-4e2e-b9f4-46c909c653f2.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"

# Small ~700 char paragraph -> 1 chunk (chunk_size default well above this).
SMALL_TEXT = (
    "The lighthouse keeper watched the storm roll in from the west. Waves "
    "crashed against the granite cliffs below, sending sheets of spray high "
    "into the salt-heavy air. He had been posted here for eleven winters "
    "and knew the moods of this coast better than his own. Tonight the "
    "wind carried a low, mournful note that meant a ship somewhere out "
    "beyond the reef was in trouble. He climbed the iron stair to the "
    "lamp room, trimmed the wick, and turned the great lens until its "
    "steady beam swept the black water. Somewhere out there a captain was "
    "counting on him, and he would not fail. Not tonight, not ever."
)
print(f"SMALL_TEXT length = {len(SMALL_TEXT)}")

created_job_ids: list = []
results = {}


def record(name, ok, evidence=""):
    results[name] = (ok, evidence)
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}: {evidence}")


def _put_settings(patch: dict):
    cur = requests.get(f"{API}/settings", timeout=15).json()
    cur.pop("_id", None)
    cur.update(patch)
    r = requests.put(f"{API}/settings", json=cur, timeout=20)
    r.raise_for_status()
    return r.json()


def _create_job(name: str, text: str = SMALL_TEXT):
    payload = {"name": name, "text": text}
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


def _poll_until_done(job_id: str, timeout_s: int = 90):
    """Poll until status is completed / failed. Returns final details dict."""
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        det = _get_details(job_id)
        st = det.get("status")
        if st != last_status:
            print(f"  job {job_id} status={st} processed={det.get('processed_chunks')}/{det.get('chunk_count')}")
            last_status = st
        if st in ("completed", "failed"):
            return det
        time.sleep(3)
    return _get_details(job_id)  # timeout -> return current state


# ---------------- Scenario A: regression on creation-time seed guards ------

def test_A1_v3_seed():
    _put_settings({"mode": "chunking", "model_id": "eleven_v3", "chunk_size": 4500})
    jid = _create_job("A1 v3 seed", text="X" * 1000 + " end.")
    time.sleep(0.3)
    det = _get_details(jid)
    seed = det.get("seed")
    model_id = (det.get("tts_config") or {}).get("model_id")
    ok = isinstance(seed, int) and 0 <= seed <= 2**31 - 1 and model_id == "eleven_v3"
    record("A1_v3_seed_nonnull", ok, f"job={jid} seed={seed} model={model_id}")
    return jid, seed


def test_A2_v2_seed():
    _put_settings({"mode": "chunking", "model_id": "eleven_multilingual_v2", "chunk_size": 4500})
    jid = _create_job("A2 v2 seed", text="Y" * 1000 + " end.")
    time.sleep(0.3)
    det = _get_details(jid)
    seed = det.get("seed")
    model_id = (det.get("tts_config") or {}).get("model_id")
    ok = isinstance(seed, int) and 0 <= seed <= 2**31 - 1 and model_id == "eleven_multilingual_v2"
    record("A2_v2_seed_nonnull", ok, f"job={jid} seed={seed} model={model_id}")
    return jid, seed


def test_A3_turbo_seed_null():
    _put_settings({"mode": "chunking", "model_id": "eleven_turbo_v2_5"})
    jid = _create_job("A3 turbo null seed", text="Z" * 1000 + " end.")
    time.sleep(0.3)
    det = _get_details(jid)
    seed = det.get("seed")
    model_id = (det.get("tts_config") or {}).get("model_id")
    ok = seed is None and model_id == "eleven_turbo_v2_5"
    record("A3_turbo_seed_null", ok, f"job={jid} seed={seed} model={model_id}")


def test_A4_studio_v3_seed_null():
    _put_settings({"mode": "studio", "model_id": "eleven_v3"})
    jid = _create_job("A4 studio v3 null seed", text="Q" * 1000 + " end.")
    time.sleep(0.3)
    det = _get_details(jid)
    seed = det.get("seed")
    cfg = det.get("tts_config") or {}
    ok = seed is None and cfg.get("mode") == "studio" and cfg.get("model_id") == "eleven_v3"
    record("A4_studio_v3_seed_null", ok, f"job={jid} seed={seed} mode={cfg.get('mode')} model={cfg.get('model_id')}")
    # Reset mode back to chunking
    _put_settings({"mode": "chunking"})


def test_A5_regenerate_reuses_seed(src_jid, src_seed, label, expected_model):
    r = requests.post(f"{API}/jobs/{src_jid}/regenerate", timeout=30)
    if r.status_code != 200:
        record(f"A5_regen_reuses_seed_{label}", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return None
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
        and regenerated_from == src_jid
        and new_model == expected_model
    )
    record(
        f"A5_regen_reuses_seed_{label}",
        ok,
        f"src_seed={src_seed} new_seed={new_seed} regen_from={regenerated_from} model={new_model}",
    )
    return new_jid


# ---------------- Scenario B: chunk_requests[i] shape after live TTS -------

def _read_backend_log_tail(nbytes: int = 200_000) -> str:
    """Return combined tail of backend stdout+stderr logs."""
    combined = []
    for path in (
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ):
        try:
            sz = os.path.getsize(path)
            with open(path, "rb") as f:
                if sz > nbytes:
                    f.seek(sz - nbytes)
                combined.append(f"===== {path} =====\n" + f.read().decode("utf-8", errors="replace"))
        except FileNotFoundError:
            pass
    return "\n".join(combined)


def test_B_v3_live():
    """Live v3 job: 1 chunk. Assert chunk_requests[0] shape after run."""
    _put_settings({"mode": "chunking", "model_id": "eleven_v3", "chunk_size": 4500})
    jid = _create_job("B v3 live small")
    print(f"[B] v3 live job id = {jid}")
    det = _poll_until_done(jid, timeout_s=90)
    status = det.get("status")
    chunk_reqs = det.get("chunk_requests") or []
    if not chunk_reqs:
        record("B_v3_chunk_shape", False, f"no chunk_requests. status={status}")
        return jid, status
    cr0 = chunk_reqs[0]
    has_seed = "seed" in cr0 and cr0["seed"] is not None
    has_request_id = "request_id" in cr0
    has_prev_ids = "previous_request_ids" in cr0

    if status == "completed":
        # Correct: seed set, request_id/prev_ids ABSENT.
        ok = has_seed and (not has_request_id) and (not has_prev_ids)
        record(
            "B_v3_chunk_shape_on_completed",
            ok,
            f"job={jid} status=completed keys={sorted(cr0.keys())} "
            f"seed={cr0.get('seed')} has_request_id={has_request_id} "
            f"has_previous_request_ids={has_prev_ids}",
        )
    elif status == "failed":
        err = str(cr0.get("error") or det.get("error") or "")
        bad_err = ("unsupported_model" in err) or ("previous_request_ids" in err)
        # PASS iff error does NOT mention the two forbidden markers.
        ok = not bad_err
        record(
            "B_v3_chunk_shape_on_failed",
            ok,
            f"job={jid} status=failed error_excerpt={err[:400]!r} "
            f"contains_unsupported_model={('unsupported_model' in err)} "
            f"contains_previous_request_ids={('previous_request_ids' in err)}",
        )
    else:
        # timeout / still processing
        record(
            "B_v3_chunk_shape_timeout",
            False,
            f"job={jid} status={status} (did not reach completed/failed in 90s) keys={sorted(cr0.keys())}",
        )
    return jid, status


def test_B_v2_live():
    _put_settings({"mode": "chunking", "model_id": "eleven_multilingual_v2", "chunk_size": 4500})
    jid = _create_job("B v2 live small")
    print(f"[B] v2 live job id = {jid}")
    det = _poll_until_done(jid, timeout_s=90)
    status = det.get("status")
    chunk_reqs = det.get("chunk_requests") or []
    if not chunk_reqs:
        record("B_v2_chunk_shape", False, f"no chunk_requests. status={status}")
        return jid, status
    cr0 = chunk_reqs[0]

    if status == "completed":
        has_seed = "seed" in cr0 and cr0["seed"] is not None
        has_request_id = "request_id" in cr0 and cr0["request_id"]
        # previous_request_ids on chunk 0 is expected [] (empty list); presence matters.
        has_prev_ids_key = "previous_request_ids" in cr0
        prev_ids = cr0.get("previous_request_ids")
        ok = has_seed and has_request_id and has_prev_ids_key and isinstance(prev_ids, list)
        record(
            "B_v2_chunk_shape_on_completed",
            ok,
            f"job={jid} status=completed keys={sorted(cr0.keys())} "
            f"seed={cr0.get('seed')} request_id={cr0.get('request_id')!r} "
            f"previous_request_ids={prev_ids!r}",
        )
    elif status == "failed":
        err = str(cr0.get("error") or det.get("error") or "")
        record(
            "B_v2_chunk_shape_on_failed",
            False,
            f"job={jid} v2 failed (informational). error_excerpt={err[:400]!r}",
        )
    else:
        record(
            "B_v2_chunk_shape_timeout",
            False,
            f"job={jid} status={status} (timed out) keys={sorted(cr0.keys())}",
        )
    return jid, status


# ---------------- Scenario C: backend log sanity ---------------------------

def test_C_log_sanity(v3_jid: str):
    """
    Check backend logs for the fingerprint of the original bug:
    HTTP 400 mentioning "unsupported_model" AND "previous_request_ids".
    """
    tail = _read_backend_log_tail(400_000)
    has_unsupported = "unsupported_model" in tail
    has_prev_ids_err = "previous_request_ids" in tail and (
        "not yet supported" in tail or "unsupported_model" in tail
    )
    # Also try to find lines mentioning the specific v3 job id
    lines_for_job = "\n".join(
        [ln for ln in tail.splitlines() if v3_jid in ln][-30:]
    )
    ok = not (has_unsupported and has_prev_ids_err)
    record(
        "C_no_unsupported_model_in_logs",
        ok,
        f"has_unsupported_model={has_unsupported} has_prev_ids_error_phrase={has_prev_ids_err}; "
        f"v3_job_log_lines_count={len([ln for ln in tail.splitlines() if v3_jid in ln])}",
    )
    if lines_for_job:
        print("---- backend log lines mentioning v3 job ----")
        print(lines_for_job[-4000:])
        print("---- end log excerpt ----")


# ---------------- Cleanup --------------------------------------------------

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

    # --- Scenario A ---
    v3_jid, v3_seed = test_A1_v3_seed()
    v2_jid, v2_seed = test_A2_v2_seed()
    test_A3_turbo_seed_null()
    test_A4_studio_v3_seed_null()
    test_A5_regenerate_reuses_seed(v3_jid, v3_seed, "v3", "eleven_v3")
    test_A5_regenerate_reuses_seed(v2_jid, v2_seed, "v2", "eleven_multilingual_v2")

    # --- Scenario B (live) ---
    live_v3_jid, live_v3_status = test_B_v3_live()
    live_v2_jid, live_v2_status = test_B_v2_live()

    # --- Scenario C (logs) ---
    test_C_log_sanity(live_v3_jid)

    # --- Cleanup ---
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
