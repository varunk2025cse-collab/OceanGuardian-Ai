import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

/// Sync state of one outbox row. Mirrors the ONLINE/OFFLINE/SYNCING/
/// SYNC_ERROR states the UI shows (see SyncService.statusStream), but at
/// the granularity of a single queued point/alert rather than the whole
/// device — a row is `failed` after a sync attempt errors, `syncing`
/// while a batch containing it is in flight, `synced` once the backend
/// has accepted it (or told us it's a duplicate — same outcome for the
/// outbox), and `pending` otherwise.
class SyncStatusValue {
  static const pending = 'pending';
  static const syncing = 'syncing';
  static const synced = 'synced';
  static const failed = 'failed';
}

/// Offline-first local store.
///
/// Two kinds of tables:
///  - `pending_locations` / `pending_sos`: an outbox queue. Every GPS fix
///    and every SOS trigger is written here FIRST, on the device, before
///    any network call is attempted. SyncService later drains this queue.
///    This is what makes the app work with zero signal for days at sea.
///  - `cache_*`: a simple key/value JSON cache for read-mostly reference
///    data (weather alerts, market prices, schemes, family status) so
///    those screens still show the last-known data when offline.
class LocalDbService {
  LocalDbService._internal();
  static final LocalDbService instance = LocalDbService._internal();

  Database? _db;

  Future<Database> get database async {
    _db ??= await _initDb();
    return _db!;
  }

  Future<Database> _initDb() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'oceanguardian_offline.db');

    return openDatabase(
      path,
      version: 3,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE pending_locations (
            client_uuid TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy_meters REAL,
            speed_mps REAL,
            heading_degrees REAL,
            altitude_meters REAL,
            battery_percent REAL,
            network_type TEXT,
            trip_id INTEGER,
            recorded_at TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            sync_status TEXT NOT NULL DEFAULT 'pending',
            retry_count INTEGER NOT NULL DEFAULT 0,
            next_retry_at TEXT
          )
        ''');
        await db.execute('''
          CREATE TABLE pending_sos (
            client_uuid TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy_meters REAL,
            battery_level_percent INTEGER,
            alert_type TEXT NOT NULL DEFAULT 'MANUAL_SOS',
            network_type TEXT,
            message TEXT,
            triggered_at TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
          )
        ''');
        await db.execute('''
          CREATE TABLE cache_kv (
            cache_key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
          )
        ''');
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          for (final ddl in [
            'ALTER TABLE pending_locations ADD COLUMN altitude_meters REAL',
            'ALTER TABLE pending_locations ADD COLUMN battery_percent REAL',
            'ALTER TABLE pending_locations ADD COLUMN network_type TEXT',
            'ALTER TABLE pending_locations ADD COLUMN trip_id INTEGER',
            "ALTER TABLE pending_locations ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending'",
            'ALTER TABLE pending_locations ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE pending_locations ADD COLUMN next_retry_at TEXT',
          ]) {
            await db.execute(ddl);
          }
          // Reconcile the new sync_status column with the pre-existing
          // boolean so rows synced before this upgrade aren't re-sent.
          await db.execute(
            "UPDATE pending_locations SET sync_status = 'synced' WHERE synced = 1",
          );
        }
        if (oldVersion < 3) {
          await db.execute("ALTER TABLE pending_sos ADD COLUMN alert_type TEXT NOT NULL DEFAULT 'MANUAL_SOS'");
          await db.execute('ALTER TABLE pending_sos ADD COLUMN network_type TEXT');
        }
      },
    );
  }

  // ---- Location outbox ----

  Future<void> queueLocation(Map<String, dynamic> dbMap) async {
    final db = await database;
    await db.insert('pending_locations', dbMap, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  /// Rows ready to sync now: still pending/failed, and (for failed rows)
  /// past their backoff `next_retry_at`. Ordered oldest-first so the
  /// upload preserves the order the fixes were actually recorded in.
  Future<List<Map<String, dynamic>>> unsyncedLocations({int limit = 200}) async {
    final db = await database;
    final nowIso = DateTime.now().toIso8601String();
    return db.query(
      'pending_locations',
      where: "sync_status IN ('pending', 'failed') AND (next_retry_at IS NULL OR next_retry_at <= ?)",
      whereArgs: [nowIso],
      limit: limit,
      orderBy: 'recorded_at ASC',
    );
  }

  Future<void> markLocationsSyncing(List<String> clientUuids) async {
    if (clientUuids.isEmpty) return;
    final db = await database;
    final batch = db.batch();
    for (final id in clientUuids) {
      batch.update('pending_locations', {'sync_status': SyncStatusValue.syncing},
          where: 'client_uuid = ?', whereArgs: [id]);
    }
    await batch.commit(noResult: true);
  }

  Future<void> markLocationsSynced(List<String> clientUuids) async {
    if (clientUuids.isEmpty) return;
    final db = await database;
    final batch = db.batch();
    for (final id in clientUuids) {
      batch.update(
        'pending_locations',
        {'synced': 1, 'sync_status': SyncStatusValue.synced, 'next_retry_at': null},
        where: 'client_uuid = ?',
        whereArgs: [id],
      );
    }
    await batch.commit(noResult: true);
  }

  /// Marks a batch as failed and schedules the next retry with exponential
  /// backoff (capped) so a persistent failure doesn't spin the sync loop.
  Future<void> markLocationsFailed(List<String> clientUuids) async {
    if (clientUuids.isEmpty) return;
    final db = await database;
    for (final id in clientUuids) {
      final rows = await db.query('pending_locations', columns: ['retry_count'], where: 'client_uuid = ?', whereArgs: [id]);
      final retryCount = rows.isEmpty ? 0 : ((rows.first['retry_count'] as int?) ?? 0);
      final nextRetryCount = retryCount + 1;
      final backoffSeconds = backoffSecondsForRetry(nextRetryCount);
      final nextRetryAt = DateTime.now().add(Duration(seconds: backoffSeconds)).toIso8601String();
      await db.update(
        'pending_locations',
        {'sync_status': SyncStatusValue.failed, 'retry_count': nextRetryCount, 'next_retry_at': nextRetryAt},
        where: 'client_uuid = ?',
        whereArgs: [id],
      );
    }
  }

  /// 30s, 60s, 120s, ... capped at 30 minutes — matches ApiConfig's base
  /// retry interval and prevents unbounded backoff on a boat that's been
  /// offline for days.
  @visibleForTesting
  static int backoffSecondsForRetry(int retryCount) {
    // Clamp the exponent input (not the result) so this stays well-defined
    // for a boat that's been failing to sync for days; the 1800s min()
    // below is what actually enforces the 30-minute cap.
    final safeCount = retryCount.clamp(1, 20);
    final seconds = 30 * (1 << (safeCount - 1));
    return seconds > 1800 ? 1800 : seconds;
  }

  Future<int> unsyncedLocationCount() async {
    final db = await database;
    final result = await db.rawQuery(
      "SELECT COUNT(*) as c FROM pending_locations WHERE sync_status != 'synced'",
    );
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// Full local trail (synced + unsynced), most recent first -- used to
  /// draw "where have I been today" on the map even with zero signal,
  /// since every fix was written here the instant it was captured.
  Future<List<Map<String, dynamic>>> recentLocations({int limit = 500}) async {
    final db = await database;
    return db.query('pending_locations', orderBy: 'recorded_at DESC', limit: limit);
  }

  // ---- SOS outbox ----

  Future<void> queueSos(Map<String, dynamic> dbMap) async {
    final db = await database;
    await db.insert('pending_sos', dbMap, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  Future<List<Map<String, dynamic>>> unsyncedSos() async {
    final db = await database;
    return db.query('pending_sos', where: 'synced = 0', orderBy: 'triggered_at ASC');
  }

  Future<void> markSosSynced(String clientUuid, {String status = 'active'}) async {
    final db = await database;
    await db.update('pending_sos', {'synced': 1, 'status': status},
        where: 'client_uuid = ?', whereArgs: [clientUuid]);
  }

  // ---- Generic JSON cache for reference data ----

  Future<void> putCache(String key, Object value) async {
    final db = await database;
    await db.insert(
      'cache_kv',
      {
        'cache_key': key,
        'value': jsonEncode(value),
        'updated_at': DateTime.now().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Returns the cached value (decoded) and when it was last refreshed, or
  /// null if nothing has ever been cached for this key.
  Future<(dynamic data, DateTime updatedAt)?> getCache(String key) async {
    final db = await database;
    final rows = await db.query('cache_kv', where: 'cache_key = ?', whereArgs: [key], limit: 1);
    if (rows.isEmpty) return null;
    final row = rows.first;
    return (jsonDecode(row['value'] as String), DateTime.parse(row['updated_at'] as String));
  }
}
