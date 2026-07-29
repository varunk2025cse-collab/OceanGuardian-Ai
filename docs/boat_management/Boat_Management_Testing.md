# Boat Management Testing Strategy
**OceanGuardian AI — Test Plan**
**Version:** 1.0

---

## 1. Test Coverage Goals

| Layer | Target Coverage |
|---|---|
| Backend unit tests | ≥ 90% on service layer |
| Backend API integration tests | 100% of endpoints |
| Security / authorization tests | 100% of role combinations |
| Flutter widget tests | All screens |
| Offline tests | All offline scenarios |
| Performance tests | List, readiness check, health score |
| Edge case tests | All business rule boundaries |

---

## 2. Backend Unit Tests

### 2.1 Boat Service Tests (`test_boat_service.py`)

```python
# Registration
test_register_boat_success
test_register_boat_duplicate_registration_number_rejected
test_register_boat_case_insensitive_duplicate_rejected  # TN-001 vs tn-001
test_register_boat_missing_required_name_rejected
test_register_boat_invalid_year_built_rejected
test_register_boat_invalid_vessel_class_rejected

# Status transitions
test_status_active_to_maintenance_allowed
test_status_active_to_inactive_allowed
test_status_maintenance_to_active_allowed
test_status_active_to_decommissioned_allowed
test_status_decommissioned_to_active_blocked
test_status_change_with_active_trip_blocked  # cannot decommission
test_status_change_creates_history_record
test_status_change_creates_audit_log

# Soft delete
test_decommission_sets_deleted_at
test_decommission_preserves_trip_history
test_decommissioned_boat_excluded_from_list
test_decommissioned_boat_accessible_by_admin

# Ownership
test_ownership_transfer_creates_pending_record
test_ownership_transfer_approved_changes_owner_id
test_ownership_transfer_rejected_leaves_owner_unchanged
test_ownership_transfer_regenerates_qr_token
test_cannot_modify_boat_during_pending_transfer

# Versioning
test_version_increments_on_update
test_version_conflict_rejected
```

### 2.2 Trip Readiness Tests (`test_boat_readiness_service.py`)

```python
test_ready_boat_returns_is_ready_true
test_inactive_boat_blocks_trip
test_expired_license_blocks_trip
test_expired_insurance_blocks_trip
test_damaged_engine_blocks_trip
test_low_fuel_returns_warning_not_block
test_missing_crew_returns_warning_not_block
test_overdue_inspection_returns_warning_not_block
test_readiness_score_100_when_all_pass
test_readiness_score_0_when_all_block
test_readiness_score_partial_with_warnings
test_offline_readiness_uses_cached_data
test_sos_not_blocked_by_readiness_check  # critical safety rule
```

### 2.3 Document Service Tests (`test_boat_document_service.py`)

```python
test_add_document_success
test_add_document_computes_file_hash
test_add_document_invalid_type_rejected
test_document_expiry_detected_correctly
test_expired_document_flagged_in_readiness
test_document_verification_by_operator
test_document_verification_by_fisherman_rejected
test_document_integrity_check_on_download
```

### 2.4 Crew Service Tests (`test_boat_crew_service.py`)

```python
test_assign_crew_success
test_assign_crew_duplicate_rejected
test_assign_captain_when_captain_exists_rejected
test_assign_primary_contact_replaces_existing
test_remove_crew_sets_removed_at
test_removed_crew_excluded_from_active_list
test_crew_visible_to_operator
test_crew_visible_to_linked_family
test_crew_not_visible_to_unlinked_family
```

### 2.5 Audit Log Tests (`test_boat_audit.py`)

```python
test_registration_creates_audit_log
test_status_change_creates_audit_log
test_document_upload_creates_audit_log
test_crew_assignment_creates_audit_log
test_audit_log_is_immutable  # no update/delete possible
test_audit_log_contains_actor_id
test_audit_log_contains_old_and_new_values
```

---

## 3. API Integration Tests

### 3.1 Authorization Tests (`test_boat_api_auth.py`)

```python
# Fisherman access
test_fisherman_can_register_own_boat
test_fisherman_can_view_own_boat
test_fisherman_cannot_view_other_fisherman_boat
test_fisherman_can_update_own_boat
test_fisherman_cannot_update_other_boat

# Operator access
test_operator_can_view_any_boat
test_operator_can_change_any_boat_status
test_operator_cannot_register_boat
test_operator_can_verify_boat

# Family access
test_family_can_view_linked_fisherman_boat
test_family_cannot_view_unlinked_fisherman_boat
test_family_cannot_update_any_boat

# Admin access
test_admin_can_view_all_boats
test_admin_can_update_any_boat
test_admin_can_approve_transfer

# Unauthenticated
test_unauthenticated_request_returns_401
test_expired_token_returns_401
```

### 3.2 Endpoint Tests (`test_boat_api_endpoints.py`)

```python
# POST /api/v2/boats
test_register_boat_returns_201
test_register_boat_returns_qr_token
test_register_boat_rate_limit_enforced

# GET /api/v2/boats
test_list_boats_pagination
test_list_boats_filter_by_status
test_list_boats_search_by_name

# GET /api/v2/boats/{id}
test_get_boat_returns_full_detail
test_get_decommissioned_boat_returns_404_for_fisherman
test_get_decommissioned_boat_returns_data_for_admin

# PATCH /api/v2/boats/{id}
test_update_boat_partial_fields
test_update_boat_version_conflict_returns_409

# DELETE /api/v2/boats/{id}
test_decommission_boat_success
test_decommission_boat_with_active_trip_returns_409

# GET /api/v2/boats/{id}/readiness
test_readiness_check_returns_blocking_issues
test_readiness_check_returns_warnings
test_readiness_check_returns_ai_recommendation

# GET /api/v2/boats/{id}/qr-code
test_qr_code_returns_token_and_payload
test_qr_scan_public_endpoint_returns_safe_data
test_qr_scan_invalid_token_returns_404
```

---

## 4. Security Tests

```python
# SQL injection
test_registration_number_sql_injection_rejected
test_boat_name_script_injection_sanitized

# Authorization bypass
test_cannot_access_boat_by_guessing_id
test_cannot_update_boat_with_another_users_token
test_cannot_approve_transfer_as_fisherman

# Rate limiting
test_registration_rate_limit_10_per_minute
test_qr_scan_rate_limit_30_per_minute

# Document security
test_document_download_requires_auth
test_document_signed_url_expires
test_document_integrity_mismatch_returns_409
test_file_type_validation_rejects_executable
test_file_size_limit_enforced_10mb
```

---

## 5. Offline Tests (Flutter)

```dart
test_boat_list_shows_cached_data_when_offline
test_boat_list_shows_offline_banner_when_offline
test_boat_registration_queued_in_outbox_when_offline
test_outbox_synced_when_connectivity_restored
test_qr_code_displayed_from_local_cache_when_offline
test_trip_readiness_uses_cached_data_when_offline
test_offline_readiness_shows_data_as_of_timestamp
test_conflict_resolution_server_wins_on_status
test_conflict_resolution_client_wins_on_fuel_log
```

---

## 6. Performance Tests

| Test | Target | Tool |
|---|---|---|
| `GET /api/v2/boats` (100 boats) | < 200ms p95 | locust |
| `GET /api/v2/boats/{id}/readiness` | < 500ms p95 | locust |
| `GET /api/v2/boats/{id}/health-score` | < 300ms p95 | locust |
| `GET /api/v2/boats/fleet/summary` (1000 boats) | < 1s p95 | locust |
| Concurrent registrations (50 simultaneous) | No duplicates, no 500s | locust |

---

## 7. Edge Cases

```python
# Boundary conditions
test_boat_name_exactly_120_chars_accepted
test_boat_name_121_chars_rejected
test_year_built_1900_accepted
test_year_built_1899_rejected
test_year_built_next_year_accepted
test_fuel_capacity_zero_rejected
test_engine_horsepower_zero_rejected

# Concurrent operations
test_concurrent_registration_same_number_only_one_succeeds
test_concurrent_status_change_version_conflict_detected
test_concurrent_crew_captain_assignment_only_one_succeeds

# Data integrity
test_decommissioned_boat_trips_still_accessible
test_transferred_boat_old_owner_loses_access
test_transferred_boat_new_owner_gains_access
test_crew_removed_from_active_trip_handled_gracefully
```

---

## 8. Definition of Done

A Boat Management feature is done when:
- [ ] All unit tests pass
- [ ] All API integration tests pass
- [ ] All authorization tests pass for all roles
- [ ] Offline behavior tested and documented
- [ ] Tamil strings reviewed by native speaker
- [ ] Accessibility audit passed (WCAG 2.1 AA)
- [ ] Performance targets met
- [ ] Audit log entries verified for all write operations
- [ ] Security review completed
- [ ] API documentation updated in Swagger
- [ ] Flutter widget test written for any new screen
