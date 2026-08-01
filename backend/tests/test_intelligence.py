from datetime import date
from app.models.boat import Boat, BoatEquipmentItem, BoatStatus
from app.schemas.intelligence import DecisionSupport, BoatHealthReport
from app.services.intelligence.boat_intelligence import BoatIntelligenceService
from app.services.intelligence.equipment_intelligence import EquipmentIntelligenceService

def test_equipment_missing_mandatory(db):
    boat = Boat(name="Test Boat", owner_id=1, status=BoatStatus.ACTIVE.value)
    db.add(boat)
    db.commit()
    
    # Missing all mandatory items
    result = EquipmentIntelligenceService.evaluate(db, boat)
    assert result.risk_level == "critical"
    assert "Missing mandatory safety equipment" in result.reason

def test_equipment_good_condition(db):
    boat = Boat(name="Test Boat", owner_id=1, status=BoatStatus.ACTIVE.value)
    db.add(boat)
    db.commit()
    
    # Add all mandatory
    items = [
        BoatEquipmentItem(boat_id=boat.id, category="life_jacket", item_name="Life Jacket", is_mandatory=True),
        BoatEquipmentItem(boat_id=boat.id, category="fire_extinguisher", item_name="Fire Ext", is_mandatory=True),
        BoatEquipmentItem(boat_id=boat.id, category="first_aid_kit", item_name="First Aid", is_mandatory=True),
        BoatEquipmentItem(boat_id=boat.id, category="distress_signal", item_name="Flares", is_mandatory=True),
        BoatEquipmentItem(boat_id=boat.id, category="navigation_light", item_name="Nav Lights", is_mandatory=True),
        BoatEquipmentItem(boat_id=boat.id, category="anchor", item_name="Anchor", is_mandatory=True),
    ]
    db.add_all(items)
    db.commit()
    
    result = EquipmentIntelligenceService.evaluate(db, boat)
    assert result.risk_level == "green"
    
def test_boat_overall_health(db):
    boat = Boat(name="Test Boat", owner_id=1, status=BoatStatus.ACTIVE.value)
    db.add(boat)
    db.commit()
    
    # Should be poor because we don't have equipment/inspections yet
    result = BoatIntelligenceService.evaluate(db, boat)
    assert isinstance(result, BoatHealthReport)
    # Trip readiness will be blocked because documents/inspections/equipment are empty (and missing mandatory equip)
    assert result.equipment_readiness.risk_level == "critical"
