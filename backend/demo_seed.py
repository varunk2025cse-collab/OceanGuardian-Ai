"""
OceanGuardian AI - Demo Mode data seeder.

Unlike seed.py (which inserts reference data - harbors, weather alerts,
market prices - directly into the database), this script drives the
REAL running API over HTTP, exactly like a real client would. That's a
deliberate choice: it proves the actual code paths work (auth, trip
lifecycle, offline-sync-style location ingestion, SOS trigger, incident
auto-creation, notification dispatch, safety evaluation), not just that
rows can be inserted.

Run after the backend is up (scripts/demo_mode.sh does this for you):
    python demo_seed.py

Idempotent: safe to re-run - existing demo accounts are logged into
rather than re-registered.

Requires SEED_DEMO_DATA=true to have been set when seed.py ran (for the
demo operator account +911234567890/rescue123) - this script prints a
clear warning and skips the operator-only steps if it can't log in as
that account, rather than silently creating a second parallel operator.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = os.environ.get("DEMO_API_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"
API_V2 = f"{BASE_URL}/api/v2"

FISHERMAN_PHONE = "+911111000001"
FAMILY_PHONE = "+911111000002"
DEMO_PASSWORD = "Demo@1234"
OPERATOR_PHONE = "+911234567890"  # created by seed.py when SEED_DEMO_DATA=true
OPERATOR_PASSWORD = "rescue123"

# Nagapattinam coast, Tamil Nadu - a real, plausible fishing harbor area
# used consistently across this project's tests and seed data.
HARBOR_LAT, HARBOR_LON = 10.766, 79.844


def wait_for_health(timeout_s: int = 30) -> None:
    print(f"Waiting for backend at {BASE_URL} ...")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                print("Backend is up.")
                return
        except Exception:
            pass
        time.sleep(1)
    print(f"ERROR: backend not reachable at {BASE_URL} after {timeout_s}s.", file=sys.stderr)
    sys.exit(1)


def register_or_login(phone: str, password: str, **register_kwargs) -> dict:
    r = httpx.post(f"{API}/auth/register", json={"phone_number": phone, "password": password, **register_kwargs})
    if r.status_code == 201:
        print(f"  Created account {phone}")
        return r.json()
    r = httpx.post(f"{API}/auth/login", json={"phone_number": phone, "password": password})
    r.raise_for_status()
    print(f"  Account {phone} already exists - logged in")
    return r.json()


def auth_headers(token_pair: dict) -> dict:
    return {"Authorization": f"Bearer {token_pair['access_token']}"}


def main():
    wait_for_health()

    print("\n1/8 - Demo fisherman + family")
    fisherman = register_or_login(
        FISHERMAN_PHONE, DEMO_PASSWORD,
        full_name="Murugan (Demo Fisherman)", role="fisherman", preferred_language="ta",
        boat_name="Sea Warrior", home_harbor="Nagapattinam",
        emergency_contact_name="Meena", emergency_contact_phone=FAMILY_PHONE,
    )
    family = register_or_login(
        FAMILY_PHONE, DEMO_PASSWORD,
        full_name="Meena (Demo Family)", role="family", preferred_language="ta",
    )
    fh = auth_headers(fisherman)
    famh = auth_headers(family)

    httpx.post(f"{API}/family/link", json={"fisherman_phone_number": FISHERMAN_PHONE, "relation": "Wife"}, headers=famh)
    print("  Family linked to fisherman")

    print("\n2/8 - Demo boat")
    boat_resp = httpx.post(f"{API}/boats/", json={
        "name": "Sea Warrior", "registration_number": "TN-NAG-DEMO-01",
        "engine_type": "Yamaha 40HP", "engine_horsepower": 40, "fuel_capacity_liters": 60.0,
        "safety_equipment": ["Life jackets x4", "Fire extinguisher"],
    }, headers=fh)
    boat_id = boat_resp.json().get("id") if boat_resp.status_code == 201 else None
    print(f"  Boat id={boat_id} (status {boat_resp.status_code} - 409 means it already exists, that's fine)")

    print("\n3/8 - Start demo trip")
    # End any pre-existing active trip from a previous run so this stays idempotent.
    httpx.post(f"{API}/trips/end", json={}, headers=fh)
    trip_resp = httpx.post(f"{API}/trips/start", json={
        "boat_id": boat_id, "start_latitude": HARBOR_LAT, "start_longitude": HARBOR_LON,
        "destination": "Demo fishing grounds",
        "estimated_return_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
    }, headers=fh)
    trip_resp.raise_for_status()
    trip_id = trip_resp.json()["id"]
    print(f"  Trip #{trip_id} started")

    print("\n4/8 - Simulated GPS trail (5 points, moving offshore over the last hour)")
    now = datetime.now(timezone.utc)
    points = []
    for i in range(5):
        lat = HARBOR_LAT + i * 0.03
        lon = HARBOR_LON + i * 0.04
        recorded_at = now - timedelta(minutes=(4 - i) * 12)
        points.append({
            "client_uuid": f"demo-trail-{trip_id}-{i}",
            "latitude": lat, "longitude": lon,
            "accuracy_meters": 8.0, "speed_mps": 3.2, "heading_degrees": 45.0,
            "battery_percent": 90 - i * 5, "network_type": "4G", "source": "MOBILE_GPS",
            "recorded_at": recorded_at.isoformat(),
        })
    sync_resp = httpx.post(f"{API}/locations/sync", json={"points": points}, headers=fh)
    sync_resp.raise_for_status()
    print(f"  {sync_resp.json()}")

    print("\n5/8 - Live weather (real Open-Meteo call, not simulated unless WEATHER_PROVIDER=simulated)")
    weather_resp = httpx.get(f"{API_V2}/weather/live", params={"lat": HARBOR_LAT, "lon": HARBOR_LON}, headers=fh, timeout=10)
    if weather_resp.status_code == 200:
        w = weather_resp.json()
        print(f"  source={w['source']} available={w['available']} wind={w.get('wind_speed_kmh')}km/h wave={w.get('wave_height_m')}m")
    else:
        print(f"  Weather call returned {weather_resp.status_code} - continuing (weather is not required for the rest of the demo)")

    print("\n6/8 - Safety state before SOS")
    safety_resp = httpx.get(f"{API_V2}/safety/", headers=fh)
    if safety_resp.status_code == 200:
        s = safety_resp.json()
        print(f"  safety_state={s['safety_state']} score={s['safety_score']} communication={s['communication_state']}")

    print("\n7/8 - Trigger demo SOS (real incident + real family notification)")
    sos_resp = httpx.post(f"{API}/sos/trigger", json={
        "client_uuid": f"demo-sos-{trip_id}",
        "latitude": HARBOR_LAT + 4 * 0.03, "longitude": HARBOR_LON + 4 * 0.04,
        "accuracy_meters": 12.0, "battery_level_percent": 68, "network_type": "OFFLINE",
        "alert_type": "ENGINE_FAILURE", "message": "Demo scenario: engine failure, drifting.",
        "triggered_at": now.isoformat(),
    }, headers=fh)
    sos_resp.raise_for_status()
    sos = sos_resp.json()
    print(f"  SOS alert #{sos['id']} triggered (type={sos['alert_type']})")

    print("\n8/8 - Operator view of the incident")
    op_login = httpx.post(f"{API}/auth/login", json={"phone_number": OPERATOR_PHONE, "password": OPERATOR_PASSWORD})
    if op_login.status_code != 200:
        print("  WARNING: could not log in as the demo operator account.")
        print("  Re-run with SEED_DEMO_DATA=true set before `python seed.py` to create it.")
    else:
        oph = auth_headers(op_login.json())
        incidents = httpx.get(f"{API_V2}/incidents/active", headers=oph).json()
        matching = [i for i in incidents if i["sos_alert_id"] == sos["id"]]
        if matching:
            incident = matching[0]
            print(f"  Incident #{incident['id']} status={incident['status']} visible on the Rescue Dashboard's Incidents page")
            ack = httpx.post(f"{API_V2}/incidents/{incident['id']}/transition",
                              json={"status": "acknowledged", "reason": "Demo: operator reviewing"}, headers=oph)
            if ack.status_code == 200:
                print(f"  Incident acknowledged by demo operator (status now: {ack.json()['status']})")

    print("\n" + "=" * 60)
    print("DEMO DATA READY")
    print("=" * 60)
    print(f"Fisherman login:  {FISHERMAN_PHONE} / {DEMO_PASSWORD}")
    print(f"Family login:     {FAMILY_PHONE} / {DEMO_PASSWORD}")
    print(f"Operator login:   {OPERATOR_PHONE} / {OPERATOR_PASSWORD}  (only if SEED_DEMO_DATA=true was set)")
    print("=" * 60)


if __name__ == "__main__":
    main()
