import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mobile/app.dart';
import 'package:mobile/core/constants/api_endpoints.dart';
import 'package:mobile/core/network/token_storage.dart';
import 'package:mobile/core/widgets/wacrm_button.dart';
import 'package:mobile/core/widgets/wacrm_card.dart';
import 'package:mobile/core/widgets/wacrm_text_field.dart';
import 'package:mobile/core/widgets/wacrm_wave_nav_bar.dart';
import 'package:mobile/features/auth/presentation/login_screen.dart';
import 'package:mobile/features/dashboard/presentation/admin_dashboard_screen.dart';
import 'package:mobile/features/dashboard/presentation/dashboard_screen.dart';
import 'package:mobile/features/navigation/main_navigation_shell.dart';
import 'package:mobile/features/support/presentation/support_customer_detail_screen.dart';
import 'package:mobile/features/support/presentation/support_customers_screen.dart';
import 'package:mobile/features/support/presentation/support_dashboard_screen.dart';
import 'package:mobile/features/support/presentation/support_followups_screen.dart';
import 'package:mobile/features/support/presentation/support_manager_dashboard_screen.dart';

/// Live Android verification against the local backend.
///
/// The emulator reaches the host backend through 10.0.2.2. These tests use the
/// real login API and the same role routing as production; they do not mock
/// AuthProvider, roles, departments or Support data.
const String _localServer = 'http://10.0.2.2:8000';

const String _supportExecUser = 'test_sup_b';
const String _supportExecPassword = 'Support@123';
const String _supportManagerUser = 'kumar';
const String _supportManagerPassword = 'kumar123';
const String _salesManagerUser = 'test_mgr';
const String _salesManagerPassword = 'TestPass@123';
const String _salesExecUser = 'test_exec';
const String _salesExecPassword = 'TestPass@123';
const String _adminUser = 'admin';
const String _adminPassword = 'admin123';

Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() condition, {
  Duration timeout = const Duration(seconds: 45),
  required String reason,
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 200));
    if (condition()) return;
    await Future<void>.delayed(const Duration(milliseconds: 120));
  }
  fail('Timed out waiting for $reason');
}

Future<void> _pumpFor(WidgetTester tester, Duration duration) async {
  final deadline = DateTime.now().add(duration);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 150));
    await Future<void>.delayed(const Duration(milliseconds: 60));
  }
}

Finder _navLabel(String label) => find.descendant(
  of: find.byType(WacrmWaveNavBar),
  matching: find.text(label),
);

Finder _supportDetailScrollable() => find
    .descendant(
      of: find.byType(SupportCustomerDetailScreen),
      matching: find.byType(Scrollable),
    )
    .first;

/// The customer detail body is a lazy ListView, so quick actions and timeline
/// entries disappear from the tree once they are far offscreen. Drag toward
/// the requested edge until the target is rebuilt, then let [ensureVisible]
/// position it for the tap/assertion.
Future<void> _revealInSupportDetail(
  WidgetTester tester,
  Finder target, {
  required bool towardTop,
}) async {
  await tester.dragUntilVisible(
    target,
    _supportDetailScrollable(),
    Offset(0, towardTop ? 320 : -320),
  );
  await tester.pump(const Duration(milliseconds: 250));
}

Future<void> _login(
  WidgetTester tester,
  String username,
  String password,
) async {
  // Fully unmount the previous test's app so provider state (including the
  // authenticated user) cannot leak into this role's login.
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump(const Duration(milliseconds: 100));
  await TokenStorage.clearSession();
  ApiEndpoints.baseUrl = _localServer;
  await tester.pumpWidget(const WaCrmApp());

  await _pumpUntil(
    tester,
    () =>
        find.text('Skip').evaluate().isNotEmpty ||
        find.byType(LoginScreen).evaluate().isNotEmpty,
    reason: 'landing or login screen',
  );

  if (find.text('Skip').evaluate().isNotEmpty) {
    // The Get Started button is only on the third carousel slide, so use the
    // always-visible Skip action to open the login form.
    await tester.tap(find.text('Skip'));
    await _pumpFor(tester, const Duration(milliseconds: 700));
  }

  await _pumpUntil(
    tester,
    () => find.byType(LoginScreen).evaluate().isNotEmpty,
    reason: 'login form',
  );

  // The server dialog stores 10.0.2.2, but initAuth intentionally falls back to
  // production for that host. Set the local base URL for this live test run.
  ApiEndpoints.baseUrl = _localServer;

  final fields = find.byType(TextFormField);
  expect(fields, findsNWidgets(2));
  await tester.enterText(fields.at(0), username);
  await tester.enterText(fields.at(1), password);
  await tester.pump(const Duration(milliseconds: 150));

  final loginButton = find.widgetWithText(ElevatedButton, 'Login');
  await tester.ensureVisible(loginButton);
  await tester.pump(const Duration(milliseconds: 150));
  await tester.tap(loginButton);

  await _pumpUntil(
    tester,
    () => find.byType(MainNavigationShell).evaluate().isNotEmpty,
    timeout: const Duration(seconds: 60),
    reason: '$username main navigation shell',
  );
  await _pumpFor(tester, const Duration(milliseconds: 800));
}

WacrmWaveNavBar _nav(WidgetTester tester) =>
    tester.widget<WacrmWaveNavBar>(find.byType(WacrmWaveNavBar));

Future<void> _openDrawer(WidgetTester tester) async {
  final scaffold = tester.state<ScaffoldState>(find.byType(Scaffold).first);
  scaffold.openDrawer();
  await _pumpFor(tester, const Duration(milliseconds: 500));
}

Future<void> _closeDrawer(WidgetTester tester) async {
  final scaffold = tester.state<ScaffoldState>(find.byType(Scaffold).first);
  scaffold.closeDrawer();
  await _pumpFor(tester, const Duration(milliseconds: 300));
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('role routing on live backend', () {
    testWidgets('Support Executive gets Support workspace only', (
      tester,
    ) async {
      await _login(tester, _supportExecUser, _supportExecPassword);

      expect(find.byType(SupportDashboardScreen), findsOneWidget);
      expect(find.byType(DashboardScreen), findsNothing);
      expect(find.byType(SupportManagerDashboardScreen), findsNothing);
      expect(_nav(tester).secondLabel, 'Customers');
      expect(_nav(tester).thirdLabel, 'Follow-ups');

      await _openDrawer(tester);
      expect(find.text('Support Customers'), findsOneWidget);
      expect(find.text('My Follow-ups'), findsOneWidget);
      expect(find.text('Backup & Handover'), findsOneWidget);
      expect(find.text('Leads Management'), findsNothing);
      expect(find.text('Field Visits'), findsNothing);
      expect(find.text('Quotations'), findsNothing);
      expect(find.text('Deals & Handoff'), findsNothing);
      expect(find.text('Reports & Funnel'), findsNothing);
      await _closeDrawer(tester);
    });

    testWidgets('Support Manager gets manager dashboard and team scope', (
      tester,
    ) async {
      await _login(tester, _supportManagerUser, _supportManagerPassword);

      expect(find.byType(SupportManagerDashboardScreen), findsOneWidget);
      expect(find.byType(SupportDashboardScreen), findsNothing);
      expect(find.byType(DashboardScreen), findsNothing);
      expect(_nav(tester).secondLabel, 'Customers');
      expect(_nav(tester).thirdLabel, 'Follow-ups');

      await _pumpUntil(
        tester,
        () => find.text('Team Snapshot').evaluate().isNotEmpty,
        reason: 'Support manager team snapshot',
      );
      expect(find.text('Team Availability'), findsOneWidget);
      expect(find.text('Follow-up Monitoring'), findsOneWidget);

      await tester.tap(_navLabel('Customers'));
      await _pumpFor(tester, const Duration(milliseconds: 500));
      expect(_nav(tester).currentIndex, 1);
      expect(find.byType(SupportCustomersScreen), findsOneWidget);
      await _pumpUntil(
        tester,
        () => find.text('Test Corp Alpha').evaluate().isNotEmpty,
        reason: 'manager team customer scope',
      );
      // The manager scope includes more customers than fit on one screen, so
      // scroll the list to verify the second company from the team data set.
      await tester.scrollUntilVisible(
        find.text('Test Corp Beta'),
        220,
        scrollable: find.byType(Scrollable).last,
      );
      expect(find.text('Test Corp Beta'), findsOneWidget);

      await _openDrawer(tester);
      expect(
        find.descendant(
          of: find.byType(Drawer),
          matching: find.text('Backup & Handover'),
        ),
        findsOneWidget,
      );
      expect(find.text('Leads Management'), findsNothing);
      await _closeDrawer(tester);
    });

    testWidgets(
      'Sales Executive keeps Sales workspace and cannot see Support tabs',
      (tester) async {
        await _login(tester, _salesExecUser, _salesExecPassword);

        expect(find.byType(DashboardScreen), findsOneWidget);
        expect(find.byType(SupportDashboardScreen), findsNothing);
        expect(_nav(tester).secondLabel, 'Leads');
        expect(_nav(tester).thirdLabel, 'Calls');

        await _openDrawer(tester);
        expect(find.text('Leads Management'), findsOneWidget);
        expect(find.text('Customers'), findsOneWidget);
        expect(find.text('Support Customers'), findsNothing);
        expect(find.text('Backup & Handover'), findsNothing);
        expect(find.text('Support Tickets'), findsNothing);
        await _closeDrawer(tester);
      },
    );

    testWidgets('Sales Manager keeps Sales workspace and manager modules', (
      tester,
    ) async {
      await _login(tester, _salesManagerUser, _salesManagerPassword);

      expect(find.byType(DashboardScreen), findsOneWidget);
      expect(find.byType(SupportDashboardScreen), findsNothing);
      expect(_nav(tester).secondLabel, 'Leads');
      expect(_nav(tester).thirdLabel, 'Calls');

      await _openDrawer(tester);
      expect(find.text('Leads Management'), findsOneWidget);
      expect(find.text('Quotations'), findsOneWidget);
      expect(find.text('Deals & Handoff'), findsOneWidget);
      expect(find.text('Support Customers'), findsNothing);
      await _closeDrawer(tester);
    });

    testWidgets('Admin gets Admin dashboard with Sales and Support access', (
      tester,
    ) async {
      await _login(tester, _adminUser, _adminPassword);

      expect(find.byType(AdminDashboardScreen), findsOneWidget);
      expect(find.byType(DashboardScreen), findsNothing);
      expect(find.byType(SupportDashboardScreen), findsNothing);
      expect(_nav(tester).secondLabel, 'Leads');
      expect(_nav(tester).thirdLabel, 'Calls');

      await _pumpUntil(
        tester,
        () => find.text('Sales Snapshot').evaluate().isNotEmpty,
        reason: 'Admin combined dashboard',
      );
      expect(find.text('Support Snapshot'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Finance Snapshot'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Finance Snapshot'), findsOneWidget);

      await _openDrawer(tester);
      final drawer = find.byType(Drawer);
      expect(
        find.descendant(of: drawer, matching: find.text('Admin Dashboard')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: drawer, matching: find.text('Support Customers')),
        findsOneWidget,
      );
      final drawerScrollable = find
          .descendant(of: drawer, matching: find.byType(Scrollable))
          .first;
      await tester.scrollUntilVisible(
        find.descendant(of: drawer, matching: find.text('Support Tickets')),
        240,
        scrollable: drawerScrollable,
      );
      expect(
        find.descendant(of: drawer, matching: find.text('Support Tickets')),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.descendant(of: drawer, matching: find.text('Backup & Handover')),
        240,
        scrollable: drawerScrollable,
      );
      expect(
        find.descendant(of: drawer, matching: find.text('Backup & Handover')),
        findsOneWidget,
      );
      await _closeDrawer(tester);
    });
  });

  testWidgets(
    'Support employee live flow: isolated customers, POC, interaction, follow-up',
    (tester) async {
      final uniqueSuffix = DateTime.now().millisecondsSinceEpoch % 100000000;
      final pocName = 'E2E Device POC $uniqueSuffix';
      final pocMobile = '98${uniqueSuffix.toString().padLeft(8, '0')}';
      final interactionMarker = 'E2E device interaction recorded $uniqueSuffix';
      final followupMarker = 'E2E device follow-up $uniqueSuffix';

      await _login(tester, _supportExecUser, _supportExecPassword);
      expect(find.byType(SupportDashboardScreen), findsOneWidget);

      await tester.tap(_navLabel('Customers'));
      await _pumpFor(tester, const Duration(milliseconds: 400));
      expect(_nav(tester).currentIndex, 1);
      expect(find.byType(SupportCustomersScreen), findsOneWidget);

      await _pumpUntil(
        tester,
        () => find.text('Test Corp Beta').evaluate().isNotEmpty,
        reason: 'assigned Support customer list',
      );
      // Department/employee isolation: this employee does not own Test Corp Alpha.
      expect(find.text('Test Corp Alpha'), findsNothing);

      await tester.tap(find.text('Test Corp Beta').first);
      await _pumpUntil(
        tester,
        () => find.byType(SupportCustomerDetailScreen).evaluate().isNotEmpty,
        reason: 'Support customer detail',
      );
      await _pumpUntil(
        tester,
        () => find.textContaining('Points of Contact').evaluate().isNotEmpty,
        reason: 'POC section',
      );

      // Add a POC and mark it primary through the real Support API.
      final addPocAction = find.text('Add POC').first;
      await tester.scrollUntilVisible(
        addPocAction,
        320,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(addPocAction);
      await _pumpUntil(
        tester,
        () => find.text('Add Point of Contact').evaluate().isNotEmpty,
        reason: 'POC sheet',
      );
      final pocFields = find.byType(TextFormField);
      await tester.enterText(pocFields.at(0), pocName);
      await tester.enterText(pocFields.at(1), pocMobile);
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.text('Primary Point of Contact'));
      await tester.pump(const Duration(milliseconds: 200));
      final savePoc = find.widgetWithText(WacrmButton, 'Add POC');
      await tester.ensureVisible(savePoc);
      await tester.tap(savePoc);
      await _pumpUntil(
        tester,
        () =>
            find.text('Add Point of Contact').evaluate().isEmpty &&
            find.text(pocName).evaluate().isNotEmpty,
        timeout: const Duration(seconds: 60),
        reason: 'saved POC in customer detail',
      );
      expect(find.text('PRIMARY'), findsWidgets);

      // Record an interaction linked to the primary POC.
      final interactionAction = find.text('Interaction');
      await _revealInSupportDetail(tester, interactionAction, towardTop: true);
      await tester.tap(interactionAction.first);
      await _pumpUntil(
        tester,
        () => find.text('Save Interaction').evaluate().isNotEmpty,
        reason: 'interaction sheet',
      );
      final interactionFields = find.byType(TextFormField);
      await tester.enterText(interactionFields.at(0), interactionMarker);
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pump(const Duration(milliseconds: 300));
      final saveInteraction = find.widgetWithText(
        WacrmButton,
        'Save Interaction',
      );
      await tester.ensureVisible(saveInteraction);
      await tester.tap(saveInteraction);
      await _pumpUntil(
        tester,
        () => find.text('Save Interaction').evaluate().isEmpty,
        timeout: const Duration(seconds: 60),
        reason: 'interaction sheet closed',
      );
      await _pumpFor(tester, const Duration(milliseconds: 700));
      await _revealInSupportDetail(
        tester,
        find.textContaining(interactionMarker),
        towardTop: false,
      );
      expect(find.textContaining(interactionMarker), findsWidgets);
      expect(find.textContaining('POC: $pocName'), findsWidgets);

      // Schedule a Support follow-up from the same customer.
      final followupAction = find.text('Follow-up');
      await _revealInSupportDetail(tester, followupAction, towardTop: true);
      await tester.tap(followupAction.first);
      await _pumpUntil(
        tester,
        () => find.text('Schedule Support Follow-up').evaluate().isNotEmpty,
        reason: 'follow-up sheet',
      );
      final followupNotes = find.widgetWithText(
        WacrmTextField,
        'Agenda / Notes',
      );
      await tester.enterText(
        find.descendant(
          of: followupNotes,
          matching: find.byType(TextFormField),
        ),
        followupMarker,
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pump(const Duration(milliseconds: 300));
      final scheduleButton = find.widgetWithText(
        WacrmButton,
        'Schedule Follow-up',
      );
      await tester.ensureVisible(scheduleButton);
      await tester.tap(scheduleButton);
      await _pumpUntil(
        tester,
        () => find.text('Schedule Support Follow-up').evaluate().isEmpty,
        timeout: const Duration(seconds: 60),
        reason: 'follow-up sheet closed',
      );
      await _revealInSupportDetail(
        tester,
        find.textContaining(followupMarker),
        towardTop: false,
      );
      expect(find.textContaining(followupMarker), findsWidgets);

      // Complete it from the dedicated Support Follow-ups tab.
      await tester.pageBack();
      await _pumpFor(tester, const Duration(milliseconds: 500));
      await tester.tap(_navLabel('Follow-ups'));
      await _pumpFor(tester, const Duration(milliseconds: 500));
      expect(_nav(tester).currentIndex, 2);
      expect(find.byType(SupportFollowupsScreen), findsOneWidget);
      await _pumpUntil(
        tester,
        () => find.textContaining(followupMarker).evaluate().isNotEmpty,
        timeout: const Duration(seconds: 60),
        reason: 'follow-up list entry',
      );
      final markerCard = find.ancestor(
        of: find.textContaining(followupMarker),
        matching: find.byType(WacrmCard),
      );
      final completeButton = find.descendant(
        of: markerCard.first,
        matching: find.byIcon(Icons.check_circle_outline_rounded),
      );
      await tester.ensureVisible(completeButton);
      await tester.tap(completeButton);
      await _pumpUntil(
        tester,
        () => find.text('Complete Follow-up').evaluate().isNotEmpty,
        reason: 'completion confirmation',
      );
      await tester.tap(find.widgetWithText(ElevatedButton, 'Complete'));
      await _pumpUntil(
        tester,
        () => find.text('Follow-up Completed!').evaluate().isNotEmpty,
        timeout: const Duration(seconds: 60),
        reason: 'completion success dialog',
      );
      expect(find.text('COMPLETED'), findsWidgets);
    },
  );
}
