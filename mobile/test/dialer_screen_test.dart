import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/calls/presentation/dialer_screen.dart';

void main() {
  testWidgets('DialerScreen keypad appends, deletes and clears digits', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: DialerScreen()));

    expect(find.text('Enter a number'), findsOneWidget);

    await tester.tap(find.text('9'));
    await tester.tap(find.text('8'));
    await tester.tap(find.text('7'));
    await tester.pump();

    expect(find.text('987'), findsOneWidget);

    await tester.tap(find.byTooltip('Delete last digit'));
    await tester.pump();
    expect(find.text('98'), findsOneWidget);

    await tester.tap(find.byTooltip('Clear'));
    await tester.pump();
    expect(find.text('Enter a number'), findsOneWidget);
  });

  testWidgets('DialerScreen long-press on zero inserts a plus', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: DialerScreen()));

    await tester.longPress(find.text('0'));
    await tester.pump();

    // One '+' is the 0-key label, one is the dialled number.
    expect(find.text('+'), findsNWidgets(2));
  });
}
