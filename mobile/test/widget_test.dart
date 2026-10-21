import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app.dart';

void main() {
  testWidgets('App smoke test builds without error', (WidgetTester tester) async {
    await tester.pumpWidget(const WaCrmApp());
    expect(find.byType(WaCrmApp), findsOneWidget);
  });
}
