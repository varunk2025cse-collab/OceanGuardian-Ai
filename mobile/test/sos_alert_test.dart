import 'package:flutter_test/flutter_test.dart';
import 'package:oceanguardian_mvp/models/sos_alert.dart';

void main() {
  test('SosAlert defaults to MANUAL_SOS and round-trips through DB map', () {
    final alert = SosAlert(
      clientUuid: 'sos-test-1',
      latitude: 9.0,
      longitude: 77.0,
      triggeredAt: DateTime.utc(2026, 1, 1, 5, 30),
      networkType: 'OFFLINE',
    );
    expect(alert.alertType, EmergencyType.manual);

    final dbMap = alert.toDbMap();
    expect(dbMap['alert_type'], 'MANUAL_SOS');
    expect(dbMap['network_type'], 'OFFLINE');

    final restored = SosAlert.fromDbMap(dbMap);
    expect(restored.alertType, EmergencyType.manual);
    expect(restored.networkType, 'OFFLINE');
  });

  test('SosAlert preserves a specific emergency type through API JSON', () {
    final alert = SosAlert(
      clientUuid: 'sos-test-2',
      latitude: 9.0,
      longitude: 77.0,
      triggeredAt: DateTime.utc(2026, 1, 1, 5, 30),
      alertType: EmergencyType.engineFailure,
    );
    final json = alert.toApiJson();
    expect(json['alert_type'], 'ENGINE_FAILURE');
    expect(EmergencyType.all, contains('ENGINE_FAILURE'));
  });
}
