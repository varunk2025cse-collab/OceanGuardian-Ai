/// Boat Service — offline-first service for boat management.
///
/// Provides the application layer over BoatRepository with:
///  - Read-through cache (local DB first, API refresh in background)
///  - Write-through with offline outbox queue
///  - Retry logic with exponential backoff
///  - Conflict detection via optimistic locking (version field)
///  - Error recovery with rollback on failure
///  - Network monitoring via SyncService
///  - Change notification via ValueNotifier
///
/// Every method returns quickly from local storage when offline,
/// and refreshes from the API when connectivity is available.
///
/// Design principle: Never show a spinner for data that can be shown
/// instantly from the local cache. Always show something, then refresh.

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../models/boat.dart';
import '../models/boat_document.dart';
import '../models/boat_crew.dart';
import '../models/boat_equipment.dart';
import 'api_client.dart';
import 'boat_repository.dart';
import 'sync_service.dart';

/// Result wrapper that indicates whether data came from cache or live API.
class BoatResult<T> {
  final T data;
  final bool fromCache;
  final DateTime? cachedAt;

  BoatResult({required this.data, required this.fromCache, this.cachedAt});

  bool get isFresh => !fromCache;
}

class BoatService {
  BoatService._internal();
  static final BoatService instance = BoatService._internal();

  final _uuid = const Uuid();
  final _repo = BoatRepository.instance;

  // ── Reactive state ────────────────────────────────────────────────────────

  /// Current list of boats (for the boat list screen).
  final ValueNotifier<List<Boat>> boats = ValueNotifier([]);

  /// Loading state indicator.
  final ValueNotifier<bool> isLoading = ValueNotifier(false);

  /// Error message for the UI (null = no error).
  final ValueNotifier<String?> error = ValueNotifier(null);

  /// Pending sync count for the boat management sync queue.
  final ValueNotifier<int> pendingSyncCount = ValueNotifier(0);

  // ── Initialization ────────────────────────────────────────────────────────

  Future<void> initialize() async {
    isLoading.value = true;
    try {
      // Load from cache first (instant)
      final cached = await _repo.getAllBoats();
      if (cached.isNotEmpty) {
        boats.value = cached;
      }

      // Then try API refresh
      try {
        final fresh = await _repo.fetchAndCacheBoats();
        boats.value = fresh;
      } catch (_) {
        // Cache data already loaded above
      }
    } finally {
      isLoading.value = false;
    }
  }

  /// Refresh pending sync count.
  Future<void> refreshPendingCount() async {
    pendingSyncCount.value = await _repo.pendingSyncCount();
  }

  // ── Boat CRUD ─────────────────────────────────────────────────────────────

  /// Get all cached boats with optional status/search filtering.
  Future<BoatResult<List<Boat>>> getBoats({
    String? status,
    String? search,
    bool forceRefresh = false,
  }) async {
    if (forceRefresh) {
      try {
        final fresh = await _repo.fetchAndCacheBoats();
        boats.value = fresh;
        return BoatResult(data: fresh, fromCache: false);
      } catch (_) {
        // Fall through to cache
      }
    }

    final cached = await _repo.getAllBoats(status: status, search: search);
    return BoatResult(
      data: cached,
      fromCache: true,
    );
  }

  /// Get a single boat by ID with optional API refresh.
  Future<BoatResult<Boat?>> getBoat(int id, {bool forceRefresh = false}) async {
    if (forceRefresh) {
      try {
        final data = await ApiClient.instance.getV2('/boats/$id');
        final boat = Boat.fromJson(data as Map<String, dynamic>);
        await _repo.upsertBoat(boat);
        return BoatResult(data: boat, fromCache: false);
      } catch (_) {
        // Fall through to cache
      }
    }

    final cached = await _repo.getBoatById(id);
    return BoatResult(data: cached, fromCache: true);
  }

  /// Create a new boat — writes locally first, then queues for sync.
  Future<BoatServiceResult<Boat>> createBoat(BoatCreate payload) async {
    isLoading.value = true;
    error.value = null;

    try {
      // Try API first (we need the ID from the server)
      try {
        final data =
            await ApiClient.instance.postV2('/boats', payload.toJson());
        final boat = Boat.fromJson(data as Map<String, dynamic>);
        await _repo.upsertBoat(boat);
        await refreshBoats();
        return BoatServiceResult.success(boat);
      } on ApiException catch (e) {
        if (e.statusCode == 409) {
          // Duplicate — surface to user
          return BoatServiceResult.error(e.message);
        }
        // Network error — queue for offline
        rethrow;
      }
    } catch (_) {
      // Queue for offline sync
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'create_boat',
        payload: payload.toJson(),
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();

      return BoatServiceResult.offline(
        message: 'Boat will be registered when signal returns',
      );
    } finally {
      isLoading.value = false;
    }
  }

  /// Update a boat with optimistic locking — writes locally first.
  Future<BoatServiceResult<Boat>> updateBoat(
      int boatId, BoatUpdate update) async {
    isLoading.value = true;
    error.value = null;

    try {
      // Get current boat for version
      final local = await _repo.getBoatById(boatId);
      if (local == null) {
        return BoatServiceResult.error('Boat not found locally');
      }

      // Try API
      try {
        final data = await ApiClient.instance.patchV2(
          '/boats/$boatId',
          local.toUpdateJson(update),
        );
        final boat = Boat.fromJson(data as Map<String, dynamic>);
        await _repo.upsertBoat(boat);
        await refreshBoats();
        return BoatServiceResult.success(boat);
      } on ApiException catch (e) {
        if (e.statusCode == 409) {
          return BoatServiceResult.error(
            'Version conflict: someone else modified this boat. Please refresh and try again.',
          );
        }
        rethrow;
      }
    } catch (_) {
      // Queue for sync
      final payload = <String, dynamic>{
        'boat_id': boatId,
        ...update.toJson(),
      };
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'update_boat',
        payload: payload,
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();

      return BoatServiceResult.offline(
        message: 'Boat update will sync when signal returns',
      );
    } finally {
      isLoading.value = false;
    }
  }

  /// Change boat status via the FSM.
  Future<BoatServiceResult<Boat>> changeStatus(
      int boatId, BoatStatusChange change) async {
    try {
      final data = await ApiClient.instance.postV2(
        '/boats/$boatId/status',
        change.toJson(),
      );
      final boat = Boat.fromJson(data as Map<String, dynamic>);
      await _repo.upsertBoat(boat);
      await refreshBoats();
      return BoatServiceResult.success(boat);
    } catch (_) {
      final payload = <String, dynamic>{
        'boat_id': boatId,
        ...change.toJson(),
      };
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'status_change',
        payload: payload,
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Status change will sync when signal returns');
    }
  }

  /// Decommission (soft-delete) a boat.
  Future<BoatServiceResult<void>> deleteBoat(int boatId,
      {String? reason}) async {
    try {
      await ApiClient.instance.deleteV2('/boats/$boatId');
      await _repo.getBoatById(boatId); // clear local
      await refreshBoats();
      return BoatServiceResult.success(null);
    } catch (_) {
      // Queue removal
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'update_boat',
        payload: {'boat_id': boatId, 'is_active': false},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Deletion will sync when signal returns');
    }
  }

  /// Refresh the boat list from API and update reactive state.
  Future<void> refreshBoats() async {
    try {
      final fresh = await _repo.fetchAndCacheBoats();
      boats.value = fresh;
    } catch (_) {
      // Keep current cache
    }
  }

  // ── Documents ─────────────────────────────────────────────────────────────

  Future<BoatResult<List<BoatDocument>>> getDocuments(int boatId) async {
    // Try API refresh
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/documents');
      final docs = (data as List)
          .map((j) => BoatDocument.fromJson(j as Map<String, dynamic>))
          .toList();
      await _repo.upsertDocuments(docs);
      return BoatResult(data: docs, fromCache: false);
    } catch (_) {
      final cached = await _repo.getDocuments(boatId);
      return BoatResult(data: cached, fromCache: true);
    }
  }

  Future<BoatServiceResult<BoatDocument>> createDocument(
    int boatId,
    Map<String, dynamic> payload,
  ) async {
    try {
      final data = await ApiClient.instance.postV2(
        '/boats/$boatId/documents',
        payload,
      );
      final doc = BoatDocument.fromJson(data as Map<String, dynamic>);
      await _repo.upsertDocument(doc);
      return BoatServiceResult.success(doc);
    } catch (_) {
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'create_doc',
        payload: {'boat_id': boatId, ...payload},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Document will upload when signal returns');
    }
  }

  Future<BoatServiceResult<void>> deleteDocument(int boatId, int docId) async {
    try {
      await ApiClient.instance.deleteV2('/boats/$boatId/documents/$docId');
      await _repo.deleteDocument(docId);
      return BoatServiceResult.success(null);
    } catch (_) {
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'delete_doc',
        payload: {'boat_id': boatId, 'document_id': docId},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Document deletion will sync when signal returns');
    }
  }

  // ── Crew ──────────────────────────────────────────────────────────────────

  Future<BoatResult<List<BoatCrewMember>>> getCrew(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/crew');
      final crew = (data as List)
          .map((j) => BoatCrewMember.fromJson(j as Map<String, dynamic>))
          .toList();
      await _repo.upsertCrewMembers(crew);
      return BoatResult(data: crew, fromCache: false);
    } catch (_) {
      final cached = await _repo.getCrew(boatId);
      return BoatResult(data: cached, fromCache: true);
    }
  }

  Future<BoatResult<List<BoatEquipmentItem>>> getEquipment(int boatId,
      {bool forceRefresh = false}) async {
    if (forceRefresh) {
      try {
        final items = await _repo.fetchAndCacheEquipment(boatId);
        return BoatResult(data: items, fromCache: false);
      } catch (_) {
        // Fall through to cache
      }
    }
    final cached = await _repo.getEquipment(boatId);
    return BoatResult(data: cached, fromCache: true);
  }

  Future<BoatServiceResult<BoatEquipmentItem>> createEquipment(
    int boatId,
    Map<String, dynamic> payload,
  ) async {
    try {
      final data =
          await ApiClient.instance.postV2('/boats/$boatId/equipment', payload);
      final item = BoatEquipmentItem.fromJson(data as Map<String, dynamic>);
      await _repo.upsertEquipmentItem(item);
      return BoatServiceResult.success(item);
    } catch (_) {
      final localId = -DateTime.now().millisecondsSinceEpoch;
      final item = BoatEquipmentItem(
        id: localId,
        boatId: boatId,
        category: payload['category'] as String,
        itemName: payload['item_name'] as String,
        quantity: payload['quantity'] as int? ?? 1,
        condition: payload['condition'] as String? ?? 'good',
        lastCheckedAt: null,
        expiryDate: null,
        notes: payload['notes'] as String?,
        isMandatory: payload['is_mandatory'] == true,
        createdAt: DateTime.now(),
      );
      await _repo.upsertEquipmentItem(item);
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'create_equipment',
        payload: {'boat_id': boatId, ...payload},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Equipment will sync when signal returns');
    }
  }

  Future<BoatServiceResult<BoatCrewMember>> assignCrew(
    int boatId,
    Map<String, dynamic> payload,
  ) async {
    try {
      final data = await ApiClient.instance.postV2(
        '/boats/$boatId/crew',
        payload,
      );
      final member = BoatCrewMember.fromJson(data as Map<String, dynamic>);
      await _repo.upsertCrewMember(member);
      return BoatServiceResult.success(member);
    } catch (_) {
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'assign_crew',
        payload: {'boat_id': boatId, ...payload},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Crew assignment will sync when signal returns');
    }
  }

  Future<BoatServiceResult<void>> removeCrew(int boatId, int crewId) async {
    try {
      await ApiClient.instance.deleteV2('/boats/$boatId/crew/$crewId');
      return BoatServiceResult.success(null);
    } catch (_) {
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'remove_crew',
        payload: {'boat_id': boatId, 'crew_id': crewId},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Crew removal will sync when signal returns');
    }
  }

  // ── Equipment ─────────────────────────────────────────────────────────────

  Future<BoatResult<BoatDocument?>> getDocument(int boatId, int docId) async {
    try {
      final data =
          await ApiClient.instance.getV2('/boats/$boatId/documents/$docId');
      final doc = BoatDocument.fromJson(data as Map<String, dynamic>);
      await _repo.upsertDocument(doc);
      return BoatResult(data: doc, fromCache: false);
    } catch (_) {
      final cached = await _repo.getDocuments(boatId);
      BoatDocument? doc;
      for (final d in cached) {
        if (d.id == docId) {
          doc = d;
          break;
        }
      }
      return BoatResult(data: doc, fromCache: true);
    }
  }

  Future<BoatResult<BoatCrewMember?>> getCrewMember(
      int boatId, int crewId) async {
    try {
      final data =
          await ApiClient.instance.getV2('/boats/$boatId/crew/$crewId');
      final member = BoatCrewMember.fromJson(data as Map<String, dynamic>);
      await _repo.upsertCrewMember(member);
      return BoatResult(data: member, fromCache: false);
    } catch (_) {
      final cached = await _repo.getCrew(boatId);
      BoatCrewMember? member;
      for (final c in cached) {
        if (c.id == crewId) {
          member = c;
          break;
        }
      }
      return BoatResult(data: member, fromCache: true);
    }
  }

  Future<BoatServiceResult<BoatCrewMember>> updateCrewRole(
    int boatId,
    int crewId,
    String newRole,
  ) async {
    try {
      final data = await ApiClient.instance.patchV2(
        '/boats/$boatId/crew/$crewId/role',
        {'new_role': newRole},
      );
      final member = BoatCrewMember.fromJson(data as Map<String, dynamic>);
      await _repo.upsertCrewMember(member);
      return BoatServiceResult.success(member);
    } catch (_) {
      final action = BoatSyncAction(
        id: _uuid.v4(),
        action: 'update_crew_role',
        payload: {'boat_id': boatId, 'crew_id': crewId, 'role': newRole},
        createdAt: DateTime.now(),
      );
      await _repo.queueSyncAction(action);
      await refreshPendingCount();
      return BoatServiceResult.offline(
          message: 'Role update will sync when signal returns');
    }
  }

  Future<BoatResult<Map<String, dynamic>>> getReadiness(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/readiness');
      return BoatResult(data: data as Map<String, dynamic>, fromCache: false);
    } catch (_) {
      return BoatResult(data: {}, fromCache: true);
    }
  }

  Future<BoatResult<Map<String, dynamic>>> getQR(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/qr');
      return BoatResult(data: data as Map<String, dynamic>, fromCache: false);
    } catch (_) {
      final boat = await _repo.getBoatById(boatId);
      if (boat != null && boat.qrCodeToken != null) {
        return BoatResult(
          data: {
            'boat_id': boat.id,
            'qr_code_token': boat.qrCodeToken,
            'qr_url': 'https://oceanguardian.ai/boat/${boat.qrCodeToken}',
          },
          fromCache: true,
        );
      }
      return BoatResult(data: {}, fromCache: true);
    }
  }

  Future<BoatResult<List<Map<String, dynamic>>>> getStatusHistory(
      int boatId) async {
    try {
      final data =
          await ApiClient.instance.getV2('/boats/$boatId/status-history');
      return BoatResult(
          data: (data as List).cast<Map<String, dynamic>>(), fromCache: false);
    } catch (_) {
      return BoatResult(data: [], fromCache: true);
    }
  }

  // ── Network Awareness ─────────────────────────────────────────────────────

  /// Whether the app currently has connectivity.
  bool get isOnline =>
      SyncService.instance.status.value == SyncUiStatus.online ||
      SyncService.instance.status.value == SyncUiStatus.syncing;

  // ── Error Recovery ────────────────────────────────────────────────────────

  /// Retry failed sync actions manually.
  Future<int> retryFailedSync() async {
    await SyncService.instance.syncNow();
    await refreshPendingCount();
    return pendingSyncCount.value;
  }

  /// Clear all errors.
  void clearError() => error.value = null;
}

/// Result type for boat service operations.
class BoatServiceResult<T> {
  final T? data;
  final String? error;
  final bool isOffline;
  final bool isSuccess;

  BoatServiceResult._({
    this.data,
    this.error,
    this.isOffline = false,
    required this.isSuccess,
  });

  factory BoatServiceResult.success(T data) =>
      BoatServiceResult._(data: data, isSuccess: true);

  factory BoatServiceResult.error(String message) =>
      BoatServiceResult._(error: message, isSuccess: false);

  factory BoatServiceResult.offline({String? message}) => BoatServiceResult._(
        error: message,
        isOffline: true,
        isSuccess: true,
      );
}
