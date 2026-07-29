"""Fix script for test and service issues."""
import os

# ── Fix service file ──────────────────────────────────────────────────────
svc_path = "app/services/boat_service.py"
with open(svc_path, "r") as f:
    svc = f.read()

# Fix 1: Add include_deleted parameter to _check_boat_access
svc = svc.replace(
    "def _check_boat_access(db: Session, boat_id: int, user: User) -> Boat:",
    "def _check_boat_access(db: Session, boat_id: int, user: User, include_deleted: bool = False) -> Boat:",
)

# Fix 2: Use include_deleted in boat fetching
old_fetch = "    boat = BoatRepository.get_by_id(db, boat_id)\n    if boat is None:"
new_fetch = (
    "    if include_deleted:\n"
    "        boat = db.query(Boat).filter(Boat.id == boat_id).first()\n"
    "    else:\n"
    "        boat = BoatRepository.get_by_id(db, boat_id)\n"
    "    if boat is None:"
)
svc = svc.replace(old_fetch, new_fetch)

# Fix 3: change_status uses include_deleted=True
svc = svc.replace(
    "            boat = _check_boat_access(db, boat_id, actor)\n\n            # ── 2. Validate new_status is a known BoatStatus",
    "            boat = _check_boat_access(db, boat_id, actor, include_deleted=True)\n\n            # ── 2. Validate new_status is a known BoatStatus",
)

with open(svc_path, "w") as f:
    f.write(svc)
print("Service file updated")

# ── Fix test file ─────────────────────────────────────────────────────────
test_path = "tests/test_boat_service.py"
with open(test_path, "r") as f:
    test = f.read()

# Fix 1: test_update_boat_no_version_still_works - save original version
old_test = (
    '    def test_update_boat_no_version_still_works(\n'
    '        self, db: Session, fisherman: User, boat: Boat\n'
    '    ):\n'
    '        """Updates without a version (backward compat) still succeed."""\n'
    '        payload = BoatV2Update(name="No Version Update")\n'
    '        updated = BoatService.update_boat(db, boat.id, payload, fisherman)\n'
    '\n'
    '        assert updated.name == "No Version Update"\n'
    '        assert updated.version == boat.version + 1'
)
new_test = (
    '    def test_update_boat_no_version_still_works(\n'
    '        self, db: Session, fisherman: User, boat: Boat\n'
    '    ):\n'
    '        """Updates without a version (backward compat) still succeed."""\n'
    '        original_version = boat.version\n'
    '        payload = BoatV2Update(name="No Version Update")\n'
    '        updated = BoatService.update_boat(db, boat.id, payload, fisherman)\n'
    '\n'
    '        assert updated.name == "No Version Update"\n'
    '        assert updated.version == original_version + 1'
)
test = test.replace(old_test, new_test)

# Fix 2: test_not_ready_soft_deleted - add db fixture
test = test.replace(
    "    def test_not_ready_soft_deleted(self, boat: Boat):",
    "    def test_not_ready_soft_deleted(self, db: Session, boat: Boat):",
)

with open(test_path, "w") as f:
    f.write(test)
print("Test file updated")

# Verify
with open(svc_path, "r") as f:
    svc_check = f.read()
assert "include_deleted" in svc_check, "Service file missing include_deleted!"
print("Verification passed: include_deleted is present in service file")
