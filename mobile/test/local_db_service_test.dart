// Tests the offline outbox's sync-status/backoff behavior (V2 core build,
// Step 4/5 — docs/V2_CORE_IMPLEMENTATION_PLAN.md) using an in-memory SQLite
// database via sqflite_common_ffi, so this runs under `flutter test`
// without a device/emulator.
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:oceanguardian_mvp/services/local_db_service.dart';
import 'package:oceanguardian_mvp/models/location_point.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  late LocalDbService db;

  setUp(() async {
    // A fresh in-memory instance per test.
    db = LocalDbService.instance;
    final opened = await db.database;
    await opened.delete('pending_locations');
  });

  LocationPoint point(String uuid, {DateTime? recordedAt}) => LocationPoint(
        clientUuid: uuid,
        latitude: 11.0,
        longitude: 79.8,
        recordedAt: recordedAt ?? DateTime.now(),
      );

  test('queued location starts pending and appears in unsyncedLocations', () async {
    await db.queueLocation(point('t-1').toDbMap());
    final pending = await db.unsyncedLocations();
    expect(pending.map((r) => r['client_uuid']), contains('t-1'));
    expect(pending.first['sync_status'], 'pending');
  });

  test('markLocationsSynced removes a row from the pending set', () async {
    await db.queueLocation(point('t-2').toDbMap());
    await db.markLocationsSynced(['t-2']);
    final pending = await db.unsyncedLocations();
    expect(pending.map((r) => r['client_uuid']), isNot(contains('t-2')));
    expect(await db.unsyncedLocationCount(), 0);
  });

  test('markLocationsFailed schedules a future retry and hides the row until then', () async {
    await db.queueLocation(point('t-3').toDbMap());
    await db.markLocationsFailed(['t-3']);

    // Immediately after failing, backoff pushes next_retry_at into the
    // future, so the row should NOT be picked up again right away.
    final pendingNow = await db.unsyncedLocations();
    expect(pendingNow.map((r) => r['client_uuid']), isNot(contains('t-3')));

    // But it still counts as outstanding work (not silently dropped).
    expect(await db.unsyncedLocationCount(), 1);
  });

  test('unsyncedLocations orders oldest-first regardless of insertion order', () async {
    final older = DateTime.now().subtract(const Duration(minutes: 10));
    final newer = DateTime.now();
    await db.queueLocation(point('t-newer', recordedAt: newer).toDbMap());
    await db.queueLocation(point('t-older', recordedAt: older).toDbMap());

    final pending = await db.unsyncedLocations();
    final uuids = pending.map((r) => r['client_uuid']).toList();
    expect(uuids.indexOf('t-older'), lessThan(uuids.indexOf('t-newer')));
  });

  test('backoff grows with retry count and is capped at 30 minutes', () {
    expect(LocalDbService.backoffSecondsForRetry(1), 30);
    expect(LocalDbService.backoffSecondsForRetry(2), 60);
    expect(LocalDbService.backoffSecondsForRetry(3), 120);
    expect(LocalDbService.backoffSecondsForRetry(10), 1800); // capped
  });
}
