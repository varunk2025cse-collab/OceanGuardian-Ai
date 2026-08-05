/// Boat Repository — offline-first data access for boat management.
///
/// Provides local SQLite storage + API sync for Boats, Documents, Crew,
/// and Equipment. Follows the same pattern as LocalDbService (offline
/// outbox + cache) extended for boat management entities.
///
/// Design:
///  - All reads hit the local DB first (instant, works offline).
///  - Writes go to SQLite + outbox queue, then attempt API sync.
///  - Background sync drains the outbox and reconciles conflicts.
///  - Uses the existing SyncService connectivity monitoring.

import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import '../models/boat.dart';
import '../models/boat_document.dart';
import '../models/boat_crew.dart';
import '../models/boat_equipment.dart';
import 'api_client.dart';
import 'local_db_service.dart';

/// Sync action queued for background processing.
class BoatSyncAction {
  final String id;
  final String
      action; // 'create_boat', 'update_boat', 'status_change', 'create_doc', 'delete_doc', 'assign_crew', 'remove_crew', 'create_equipment'
  final Map<String, dynamic> payload;
  final DateTime createdAt;

  BoatSyncAction({
    required this.id,
    required this.action,
    required this.payload,
    required this.createdAt,
  });

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'action': action,
        'payload': jsonEncode(payload),
        'created_at': createdAt.toIso8601String(),
        'sync_status': 'pending',
        'retry_count': 0,
        'next_retry_at': null,
      };

  factory BoatSyncAction.fromDbMap(Map<String, dynamic> map) => BoatSyncAction(
        id: map['id'] as String,
        action: map['action'] as String,
        payload: jsonDecode(map['payload'] as String) as Map<String, dynamic>,
        createdAt: DateTime.parse(map['created_at'] as String),
      );
}

class BoatRepository {
  BoatRepository._internal();
  static final BoatRepository instance = BoatRepository._internal();

  // ── Database helpers ─────────────────────────────────────────────────────

  Future<Database> get _db async => LocalDbService.instance.database;

  Future<void> _ensureBoatTables() async {
    final db = await _db;
    // Boat table
    await db.execute('''
      CREATE TABLE IF NOT EXISTS boats (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        registration_number TEXT,
        status TEXT NOT NULL DEFAULT 'registered',
        vessel_class TEXT,
        hull_material TEXT,
        color TEXT,
        length_meters REAL,
        beam_meters REAL,
        draft_meters REAL,
        year_built INTEGER,
        engine_type TEXT,
        engine_make TEXT,
        engine_model TEXT,
        engine_serial_number TEXT,
        engine_year INTEGER,
        engine_horsepower INTEGER,
        fuel_capacity_liters REAL,
        home_harbor_id INTEGER,
        verification_status TEXT NOT NULL DEFAULT 'unverified',
        verified_at TEXT,
        qr_code_token TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT
      )
    ''');
    // Boat documents table
    await db.execute('''
      CREATE TABLE IF NOT EXISTS boat_documents (
        id INTEGER PRIMARY KEY,
        boat_id INTEGER NOT NULL,
        document_type TEXT NOT NULL,
        document_number TEXT,
        issuing_authority TEXT,
        issue_date TEXT,
        expiry_date TEXT,
        file_url TEXT,
        file_hash TEXT,
        is_verified INTEGER NOT NULL DEFAULT 0,
        verified_at TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
      )
    ''');
    // Boat crew table
    await db.execute('''
      CREATE TABLE IF NOT EXISTS boat_crew (
        id INTEGER PRIMARY KEY,
        boat_id INTEGER NOT NULL,
        user_id INTEGER,
        full_name TEXT NOT NULL,
        phone_number TEXT,
        role TEXT NOT NULL,
        is_primary_contact INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        assigned_at TEXT NOT NULL,
        removed_at TEXT,
        removal_reason TEXT
      )
    ''');
    // Boat equipment table
    await db.execute('''
      CREATE TABLE IF NOT EXISTS boat_equipment (
        id INTEGER PRIMARY KEY,
        boat_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        condition TEXT NOT NULL DEFAULT 'good',
        last_checked_at TEXT,
        expiry_date TEXT,
        notes TEXT,
        is_mandatory INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
      )
    ''');
    // Sync outbox table for offline queue
    await db.execute('''
      CREATE TABLE IF NOT EXISTS boat_sync_outbox (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        sync_status TEXT NOT NULL DEFAULT 'pending',
        retry_count INTEGER NOT NULL DEFAULT 0,
        next_retry_at TEXT
      )
    ''');
  }

  // ── Boat CRUD ────────────────────────────────────────────────────────────

  Future<List<Boat>> getAllBoats({String? status, String? search}) async {
    await _ensureBoatTables();
    final db = await _db;
    var query = 'SELECT * FROM boats WHERE is_active = 1';
    final params = <dynamic>[];
    if (status != null && status.isNotEmpty) {
      query += ' AND status = ?';
      params.add(status);
    }
    if (search != null && search.isNotEmpty) {
      query += ' AND (name LIKE ? OR registration_number LIKE ?)';
      params.addAll(['%$search%', '%$search%']);
    }
    query += ' ORDER BY created_at DESC';
    final rows = await db.rawQuery(query, params);
    return rows.map((r) => Boat.fromDbMap(r)).toList();
  }

  Future<Boat?> getBoatById(int id) async {
    await _ensureBoatTables();
    final db = await _db;
    final rows = await db.query('boats', where: 'id = ?', whereArgs: [id]);
    if (rows.isEmpty) return null;
    return Boat.fromDbMap(rows.first);
  }

  Future<void> upsertBoat(Boat boat) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.insert('boats', boat.toDbMap(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertBoats(List<Boat> boats) async {
    await _ensureBoatTables();
    final db = await _db;
    final batch = db.batch();
    for (final boat in boats) {
      batch.insert('boats', boat.toDbMap(),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  // ── Boat Documents ───────────────────────────────────────────────────────

  Future<List<BoatDocument>> getDocuments(int boatId) async {
    await _ensureBoatTables();
    final db = await _db;
    final rows = await db.query('boat_documents',
        where: 'boat_id = ?', whereArgs: [boatId], orderBy: 'created_at DESC');
    return rows.map((r) => BoatDocument.fromDbMap(r)).toList();
  }

  Future<void> upsertDocument(BoatDocument doc) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.insert('boat_documents', doc.toDbMap(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertDocuments(List<BoatDocument> docs) async {
    await _ensureBoatTables();
    final db = await _db;
    final batch = db.batch();
    for (final doc in docs) {
      batch.insert('boat_documents', doc.toDbMap(),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> deleteDocument(int docId) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.delete('boat_documents', where: 'id = ?', whereArgs: [docId]);
  }

  // ── Boat Crew ─────────────────────────────────────────────────────────────

  Future<List<BoatCrewMember>> getCrew(int boatId,
      {bool includeInactive = false}) async {
    await _ensureBoatTables();
    final db = await _db;
    var query = 'SELECT * FROM boat_crew WHERE boat_id = ?';
    final params = <dynamic>[boatId];
    if (!includeInactive) {
      query += ' AND is_active = 1';
    }
    query += ' ORDER BY assigned_at ASC';
    final rows = await db.rawQuery(query, params);
    return rows.map((r) => BoatCrewMember.fromDbMap(r)).toList();
  }

  Future<void> upsertCrewMember(BoatCrewMember member) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.insert('boat_crew', member.toDbMap(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertCrewMembers(List<BoatCrewMember> members) async {
    await _ensureBoatTables();
    final db = await _db;
    final batch = db.batch();
    for (final member in members) {
      batch.insert('boat_crew', member.toDbMap(),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  // ── Boat Equipment ────────────────────────────────────────────────────────

  Future<List<BoatEquipmentItem>> getEquipment(int boatId,
      {String? category}) async {
    await _ensureBoatTables();
    final db = await _db;
    var query = 'SELECT * FROM boat_equipment WHERE boat_id = ?';
    final params = <dynamic>[boatId];
    if (category != null) {
      query += ' AND category = ?';
      params.add(category);
    }
    query += ' ORDER BY category, item_name';
    final rows = await db.rawQuery(query, params);
    return rows.map((r) => BoatEquipmentItem.fromDbMap(r)).toList();
  }

  Future<void> upsertEquipmentItem(BoatEquipmentItem item) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.insert('boat_equipment', item.toDbMap(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertEquipment(List<BoatEquipmentItem> items) async {
    await _ensureBoatTables();
    final db = await _db;
    final batch = db.batch();
    for (final item in items) {
      batch.insert('boat_equipment', item.toDbMap(),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  // ── Sync Outbox ───────────────────────────────────────────────────────────

  /// Queue a boat action for background sync (offline write).
  Future<void> queueSyncAction(BoatSyncAction action) async {
    await _ensureBoatTables();
    final db = await _db;
    await db.insert('boat_sync_outbox', action.toDbMap(),
        conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  /// Get pending sync actions, ordered oldest-first.
  Future<List<BoatSyncAction>> getPendingSyncActions({int limit = 50}) async {
    await _ensureBoatTables();
    final db = await _db;
    final now = DateTime.now().toIso8601String();
    final rows = await db.rawQuery('''
      SELECT * FROM boat_sync_outbox
      WHERE sync_status IN ('pending', 'failed')
        AND (next_retry_at IS NULL OR next_retry_at <= ?)
      ORDER BY created_at ASC
      LIMIT ?
    ''', [now, limit]);
    return rows.map((r) => BoatSyncAction.fromDbMap(r)).toList();
  }

  /// Mark a sync action as successfully synced.
  Future<void> markSyncDone(String id) async {
    final db = await _db;
    await db.delete('boat_sync_outbox', where: 'id = ?', whereArgs: [id]);
  }

  /// Mark a sync action as failed with backoff.
  Future<void> markSyncFailed(String id) async {
    final db = await _db;
    final rows = await db.query('boat_sync_outbox',
        columns: ['retry_count'], where: 'id = ?', whereArgs: [id]);
    final retryCount =
        rows.isEmpty ? 0 : ((rows.first['retry_count'] as int?) ?? 0) + 1;
    final backoffSeconds = _backoffForRetry(retryCount);
    final nextRetryAt =
        DateTime.now().add(Duration(seconds: backoffSeconds)).toIso8601String();
    await db.update(
      'boat_sync_outbox',
      {
        'sync_status': 'failed',
        'retry_count': retryCount,
        'next_retry_at': nextRetryAt
      },
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  /// Number of pending sync items.
  Future<int> pendingSyncCount() async {
    await _ensureBoatTables();
    final db = await _db;
    final result = await db.rawQuery(
        "SELECT COUNT(*) as c FROM boat_sync_outbox WHERE sync_status != 'synced'");
    return Sqflite.firstIntValue(result) ?? 0;
  }

  // ── API Sync ──────────────────────────────────────────────────────────────

  /// Fetch all boats for the current user from the API and cache locally.
  Future<List<Boat>> fetchAndCacheBoats() async {
    try {
      final data = await ApiClient.instance.getV2('/boats?page_size=100');
      final boats = (data['data'] as List)
          .map((j) => Boat.fromJson(j as Map<String, dynamic>))
          .toList();
      await upsertBoats(boats);
      return boats;
    } catch (_) {
      // Offline — return whatever is cached
      return getAllBoats();
    }
  }

  /// Fetch document list from API and cache locally.
  Future<List<BoatDocument>> fetchAndCacheDocuments(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/documents');
      final docs = (data as List)
          .map((j) => BoatDocument.fromJson(j as Map<String, dynamic>))
          .toList();
      await upsertDocuments(docs);
      return docs;
    } catch (_) {
      return getDocuments(boatId);
    }
  }

  /// Fetch crew from API and cache locally.
  Future<List<BoatCrewMember>> fetchAndCacheCrew(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/crew');
      final crew = (data as List)
          .map((j) => BoatCrewMember.fromJson(j as Map<String, dynamic>))
          .toList();
      await upsertCrewMembers(crew);
      return crew;
    } catch (_) {
      return getCrew(boatId);
    }
  }

  /// Fetch equipment from API and cache locally.
  Future<List<BoatEquipmentItem>> fetchAndCacheEquipment(int boatId) async {
    try {
      final data = await ApiClient.instance.getV2('/boats/$boatId/equipment');
      final items = (data as List)
          .map((j) => BoatEquipmentItem.fromJson(j as Map<String, dynamic>))
          .toList();
      await upsertEquipment(items);
      return items;
    } catch (_) {
      return getEquipment(boatId);
    }
  }

  /// Process the sync outbox — called by SyncService periodically.
  Future<void> processSyncQueue() async {
    final actions = await getPendingSyncActions();
    for (final action in actions) {
      try {
        await _executeSyncAction(action);
        await markSyncDone(action.id);
      } catch (_) {
        await markSyncFailed(action.id);
      }
    }
  }

  Future<void> _executeSyncAction(BoatSyncAction action) async {
    switch (action.action) {
      case 'create_boat':
        await ApiClient.instance.postV2('/boats', action.payload);
        break;
      case 'update_boat':
        final boatId = action.payload['boat_id'];
        await ApiClient.instance.patchV2('/boats/$boatId', action.payload);
        break;
      case 'status_change':
        final boatId = action.payload['boat_id'];
        await ApiClient.instance
            .postV2('/boats/$boatId/status', action.payload);
        break;
      case 'create_doc':
        final boatId = action.payload['boat_id'];
        await ApiClient.instance
            .postV2('/boats/$boatId/documents', action.payload);
        break;
      case 'delete_doc':
        final boatId = action.payload['boat_id'];
        final docId = action.payload['document_id'];
        await ApiClient.instance.deleteV2('/boats/$boatId/documents/$docId');
        break;
      case 'assign_crew':
        final boatId = action.payload['boat_id'];
        await ApiClient.instance.postV2('/boats/$boatId/crew', action.payload);
        break;
      case 'remove_crew':
        final boatId = action.payload['boat_id'];
        final crewId = action.payload['crew_id'];
        await ApiClient.instance.deleteV2('/boats/$boatId/crew/$crewId');
        break;
      case 'create_equipment':
        final boatId = action.payload['boat_id'];
        await ApiClient.instance
            .postV2('/boats/$boatId/equipment', action.payload);
        break;
    }
  }

  /// Exponential backoff capped at 30 minutes.
  int _backoffForRetry(int retryCount) {
    final safeCount = retryCount.clamp(1, 20);
    final seconds = 30 * (1 << (safeCount - 1));
    return seconds > 1800 ? 1800 : seconds;
  }
}
