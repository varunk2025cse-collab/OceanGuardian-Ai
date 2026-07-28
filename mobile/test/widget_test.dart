// Minimal smoke test: the app boots to the splash screen without throwing.
// Run with: flutter test
import 'package:flutter_test/flutter_test.dart';
import 'package:oceanguardian_mvp/main.dart';

void main() {
  testWidgets('App boots to splash screen', (WidgetTester tester) async {
    await tester.pumpWidget(const OceanGuardianApp());
    expect(find.text('OceanGuardian'), findsOneWidget);
  });
}
