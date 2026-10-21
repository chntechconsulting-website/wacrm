import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app.dart';
import 'package:mobile/features/auth/presentation/landing_welcome_screen.dart';

void main() {
  testWidgets('App smoke test builds without error', (WidgetTester tester) async {
    await tester.pumpWidget(const WaCrmApp());
    expect(find.byType(WaCrmApp), findsOneWidget);
  });

  testWidgets('LandingWelcomeScreen displays slide 1 content and supports swiping between slides', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: LandingWelcomeScreen(),
      ),
    );

    // Initial slide 1 should show brand subtitle and Skip button
    expect(find.text('Manage Leads. Close Deals. Grow Together.'), findsOneWidget);
    expect(find.text('Skip'), findsOneWidget);
    expect(find.text('Powered by'), findsOneWidget);
    expect(find.text('CHN'), findsOneWidget);

    // Swipe to Slide 2
    await tester.drag(find.byType(PageView), const Offset(-500, 0));
    await tester.pumpAndSettle();

    // Now slide 2 metrics should be visible
    expect(find.text('New Leads'), findsOneWidget);
    expect(find.text('Follow-ups'), findsOneWidget);
    expect(find.text('Converted'), findsOneWidget);

    // Swipe to Slide 3
    await tester.drag(find.byType(PageView), const Offset(-500, 0));
    await tester.pumpAndSettle();

    // Now slide 3 button and features should be visible
    expect(find.text('Get Started'), findsOneWidget);
    expect(find.text('Quotation'), findsOneWidget);
  });
}
