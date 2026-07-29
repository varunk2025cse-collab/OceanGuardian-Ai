"""Fix indentation error in boat_service.py."""
import ast

path = "app/services/boat_service.py"
with open(path, "r") as f:
    content = f.read()

# The broken section looks like:
#     if include_deleted:
#         boat = db.query(Boat).filter(Boat.id == boat_id).first()
#     else:
#         if include_deleted:
#         boat = db.query(Boat).filter(Boat.id == boat_id).first()
#     else:
#         boat = BoatRepository.get_by_id(db, boat_id)
#     if boat is None:

# Replace with correct:
#     if include_deleted:
#         boat = db.query(Boat).filter(Boat.id == boat_id).first()
#     else:
#         boat = BoatRepository.get_by_id(db, boat_id)
#     if boat is None:

broken = (
    "    if include_deleted:\n"
    "        boat = db.query(Boat).filter(Boat.id == boat_id).first()\n"
    "    else:\n"
    "        if include_deleted:\n"
    "        boat = db.query(Boat).filter(Boat.id == boat_id).first()\n"
    "    else:\n"
    "        boat = BoatRepository.get_by_id(db, boat_id)\n"
    "    if boat is None:"
)

fixed = (
    "    if include_deleted:\n"
    "        boat = db.query(Boat).filter(Boat.id == boat_id).first()\n"
    "    else:\n"
    "        boat = BoatRepository.get_by_id(db, boat_id)\n"
    "    if boat is None:"
)

if broken in content:
    content = content.replace(broken, fixed)
    with open(path, "w") as f:
        f.write(content)
    print("Fixed broken indentation block")
else:
    print("Broken block not found - checking current state")
    # Try to find what's there
    for i, line in enumerate(content.split('\n')):
        if 'include_deleted' in line or 'boat = db.query' in line or 'BoatRepository.get_by_id' in line:
            if 185 <= i <= 200:
                print(f"  Line {i}: {line}")

# Verify syntax
try:
    ast.parse(content)
    print("Syntax check: PASSED")
except SyntaxError as e:
    print(f"Syntax check: FAILED - {e}")
