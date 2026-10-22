import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:mobile/app.dart';
import 'package:mobile/features/auth/presentation/landing_welcome_screen.dart';
import 'package:mobile/features/auth/presentation/login_screen.dart';
import 'package:mobile/features/auth/providers/auth_provider.dart';
import 'package:mobile/features/leads/models/lead_model.dart';
import 'package:mobile/features/leads/presentation/lead_create_edit_screen.dart';
import 'package:mobile/features/leads/presentation/lead_detail_screen.dart';
import 'package:mobile/features/leads/presentation/leads_list_screen.dart';
import 'package:mobile/features/leads/providers/leads_provider.dart';
import 'package:mobile/core/widgets/wacrm_wave_nav_bar.dart';
import 'package:mobile/features/notifications/providers/notifications_provider.dart';
import 'package:mobile/features/settings/presentation/privacy_policy_screen.dart';
import 'package:mobile/features/settings/presentation/settings_screen.dart';
import 'package:mobile/features/settings/presentation/terms_and_conditions_screen.dart';

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

    // Initial slide 1 should show brand subtitle, Skip button, badges, and Powered by footer
    expect(find.text('Manage Leads. Close Deals. Grow Together.'), findsOneWidget);
    expect(find.text('Skip'), findsOneWidget);
    expect(find.text('Powered by'), findsOneWidget);
    expect(find.byType(Image), findsWidgets);
    expect(find.byIcon(Icons.flag_rounded), findsOneWidget);
    expect(find.byIcon(Icons.person_rounded), findsOneWidget);
    expect(find.byIcon(Icons.pie_chart_rounded), findsOneWidget);

    // Swipe to Slide 2
    await tester.drag(find.byType(PageView), const Offset(-500, 0));
    await tester.pumpAndSettle();

    // Now slide 2 metrics should be visible
    expect(find.text('New Leads'), findsOneWidget);
    expect(find.text('Follow-ups'), findsOneWidget);
    expect(find.text('Converted'), findsOneWidget);
    expect(find.text('24'), findsOneWidget);
    expect(find.text('18'), findsOneWidget);
    expect(find.text('5'), findsOneWidget);
    expect(find.text('↑ 12%'), findsOneWidget);
    expect(find.text('↑ 8%'), findsOneWidget);
    expect(find.text('↑ 25%'), findsOneWidget);
    expect(find.byIcon(Icons.trending_up_rounded), findsOneWidget);

    // Swipe to Slide 3
    await tester.drag(find.byType(PageView), const Offset(-500, 0));
    await tester.pumpAndSettle();

    // Now slide 3 button and features should be visible
    expect(find.text('Get Started'), findsOneWidget);
    expect(find.text('Quotation'), findsOneWidget);
  });

  testWidgets('LoginScreen renders redesigned header, mini feature badges, login card and Google button', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AuthProvider(),
        child: const MaterialApp(
          home: LoginScreen(),
        ),
      ),
    );

    // Header mini features
    expect(find.text('Leads'), findsOneWidget);
    expect(find.text('Deals'), findsOneWidget);
    expect(find.text('Growth'), findsOneWidget);

    // Card texts
    expect(find.text('Sign in to continue to your CRM'), findsOneWidget);
    expect(find.text('Remember me'), findsOneWidget);
    expect(find.text('Forgot Password?'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
    expect(find.text('Powered by'), findsOneWidget);
  });

  testWidgets('LandingWelcomeScreen adapts cleanly without overflow on short Android screen (360x640)', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      const MaterialApp(
        home: LandingWelcomeScreen(),
      ),
    );

    // Slide 1 on compact screen
    expect(find.text('Manage Leads. Close Deals. Grow Together.'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 2
    await tester.drag(find.byType(PageView), const Offset(-300, 0));
    await tester.pumpAndSettle();
    expect(find.text('New Leads'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 3
    await tester.drag(find.byType(PageView), const Offset(-300, 0));
    await tester.pumpAndSettle();
    expect(find.text('Get Started'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('LandingWelcomeScreen adapts cleanly without overflow on tall Android screen (412x915)', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(412, 915);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      const MaterialApp(
        home: LandingWelcomeScreen(),
      ),
    );

    // Slide 1 on tall screen
    expect(find.text('Manage Leads. Close Deals. Grow Together.'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 2
    await tester.drag(find.byType(PageView), const Offset(-350, 0));
    await tester.pumpAndSettle();
    expect(find.text('New Leads'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 3
    await tester.drag(find.byType(PageView), const Offset(-350, 0));
    await tester.pumpAndSettle();
    expect(find.text('Get Started'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('LandingWelcomeScreen adapts cleanly without overflow on mid-size screen (390x844)', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      const MaterialApp(
        home: LandingWelcomeScreen(),
      ),
    );

    expect(find.text('Manage Leads. Close Deals. Grow Together.'), findsOneWidget);
    expect(find.text('Skip'), findsOneWidget);
    expect(find.text('Powered by'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 2
    await tester.drag(find.byType(PageView), const Offset(-300, 0));
    await tester.pumpAndSettle();
    expect(find.text('New Leads'), findsOneWidget);
    expect(tester.takeException(), isNull);

    // Swipe to Slide 3
    await tester.drag(find.byType(PageView), const Offset(-300, 0));
    await tester.pumpAndSettle();
    expect(find.text('Get Started'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('LeadsListScreen renders hero banner, search bar, and filter tabs', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthProvider()),
          ChangeNotifierProvider(create: (_) => LeadsProvider()),
        ],
        child: const MaterialApp(
          home: LeadsListScreen(),
        ),
      ),
    );

    // Hero banner texts
    expect(find.text('Leads'), findsWidgets);
    expect(find.text('Find new opportunities,\nturn them into customers.'), findsOneWidget);

    // Search bar hint
    expect(find.text('Search leads, company, phone...'), findsOneWidget);

    // Filter tabs
    expect(find.text('All Leads'), findsOneWidget);
    expect(find.text('New'), findsOneWidget);
    expect(find.text('In Progress'), findsOneWidget);
    expect(find.text('Hot'), findsOneWidget);
    expect(find.text('Won'), findsOneWidget);
  });

  testWidgets('LeadDetailScreen renders profile card, 5 quick actions, tabs, basic info, and status', (WidgetTester tester) async {
    final mockLead = LeadModel(
      id: 101,
      name: 'Arun Kumar',
      phone: '+91 98765 43210',
      email: 'arun@techsolutions.com',
      company: 'Tech Solutions Pvt Ltd',
      source: 'Website',
      status: 'IN_PROGRESS',
      priority: 'HOT',
      requirement: 'Corporate Software Solutions',
      assignedToName: 'Chandra Mohan',
      createdAt: '2026-10-16T10:00:00Z',
    );

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthProvider()),
          ChangeNotifierProvider(create: (_) => LeadsProvider()),
        ],
        child: MaterialApp(
          home: LeadDetailScreen(lead: mockLead),
        ),
      ),
    );

    // Profile card
    expect(find.text('Tech Solutions Pvt Ltd'), findsOneWidget);
    expect(find.text('Corporate Software Solutions'), findsOneWidget);
    expect(find.text('Hot Lead'), findsOneWidget);

    // 5 Quick actions
    expect(find.text('Call'), findsOneWidget);
    expect(find.text('WhatsApp'), findsOneWidget);
    expect(find.text('Email'), findsNWidgets(2));
    expect(find.text('Map'), findsOneWidget);
    expect(find.text('More'), findsWidgets);

    // Sub nav tabs
    expect(find.text('Overview'), findsOneWidget);
    expect(find.text('Activities'), findsOneWidget);
    expect(find.text('Quotes'), findsOneWidget);
    expect(find.text('Files'), findsOneWidget);

    // Basic information
    expect(find.text('Basic Information'), findsOneWidget);
    expect(find.text('Contact Person'), findsOneWidget);
    expect(find.text('+91 98765 43210'), findsOneWidget);
    expect(find.text('arun@techsolutions.com'), findsOneWidget);

    // Lead status & Update status button
    expect(find.text('Lead Status'), findsOneWidget);
    expect(find.text('Update Status'), findsOneWidget);
  });

  testWidgets('LeadsListScreen hamburger menu opens WacrmDrawer with modules and Sign Out', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthProvider()),
          ChangeNotifierProvider(create: (_) => LeadsProvider()),
        ],
        child: const MaterialApp(
          home: LeadsListScreen(),
        ),
      ),
    );

    // Menu icon is visible
    final menuButton = find.byTooltip('Navigation Menu');
    expect(menuButton, findsOneWidget);

    // Tap menu button and advance animation
    await tester.tap(menuButton);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 600));

    // Drawer is now fully opened
    expect(find.text('MAIN NAVIGATION'), findsOneWidget);
    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Leads Management'), findsOneWidget);
    expect(find.text('Follow-ups & Reminders'), findsOneWidget);
    expect(find.text('Customers'), findsOneWidget);
    expect(find.text('Sign Out'), findsOneWidget);

    // Tap Sign Out in the pinned drawer footer opens confirmation dialog
    await tester.tap(find.text('Sign Out'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 600));

    expect(find.text('Confirm Sign Out'), findsOneWidget);
    expect(find.text('Are you sure you want to sign out of WACRM?'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);

    // Confirm sign out in dialog
    await tester.tap(find.widgetWithText(ElevatedButton, 'Sign Out'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // Dialog dismissed
    expect(find.text('Confirm Sign Out'), findsNothing);
  });

  testWidgets('LeadCreateEditScreen renders all 5 web-synchronized detail sections', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => LeadsProvider()),
          ChangeNotifierProvider(create: (_) => AuthProvider()),
        ],
        child: const MaterialApp(
          home: LeadCreateEditScreen(),
        ),
      ),
    );

    // Title & Header
    expect(find.text('Create New Lead'), findsOneWidget);
    expect(find.text('Manual Lead Registration'), findsOneWidget);

    // Section 1: Contact Information
    expect(find.text('Contact Information'), findsOneWidget);
    expect(find.text('First Name *'), findsOneWidget);
    expect(find.text('Last Name *'), findsOneWidget);
    expect(find.text('Mobile Number *'), findsOneWidget);
    expect(find.text('WhatsApp Number'), findsOneWidget);
    expect(find.text('Email Address'), findsOneWidget);
    expect(find.text('Designation'), findsOneWidget);

    // Section 2: Company Information
    expect(find.text('Company Information'), findsOneWidget);
    expect(find.text('Company Name'), findsOneWidget);
    expect(find.text('Industry'), findsOneWidget);
    expect(find.text('Website'), findsOneWidget);
    expect(find.text('Company Size'), findsOneWidget);
    expect(find.text('City'), findsOneWidget);
    expect(find.text('State'), findsOneWidget);

    // Section 3: Lead Details & Assignment
    expect(find.text('Lead Details & Assignment'), findsOneWidget);
    expect(find.text('Lead Source'), findsOneWidget);
    expect(find.text('Initial Status'), findsOneWidget);
    expect(find.text('Campaign Name'), findsOneWidget);
    expect(find.text('Rating'), findsOneWidget);
    expect(find.text('Priority'), findsOneWidget);

    // Section 4: Requirement Notes
    expect(find.text('Requirement & Discovery Notes'), findsOneWidget);

    // Section 5: Follow-up Schedule
    expect(find.text('Follow-up Schedule'), findsOneWidget);
    expect(find.text('Follow-up Date'), findsOneWidget);
    expect(find.text('Follow-up Time'), findsOneWidget);

    // Action buttons
    expect(find.text('Cancel'), findsOneWidget);
    expect(find.text('Create Lead'), findsOneWidget);
  });

  testWidgets('WacrmWaveNavBar displays Settings and has NO More item', (WidgetTester tester) async {
    int selectedIndex = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          bottomNavigationBar: WacrmWaveNavBar(
            currentIndex: selectedIndex,
            onTap: (idx) => selectedIndex = idx,
            onAdd: () {},
          ),
        ),
      ),
    );

    // Verify 4 main items
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Leads'), findsOneWidget);
    expect(find.text('Calls'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);

    // Strict requirement: NO "More" text or icon anywhere in navbar
    expect(find.text('More'), findsNothing);
    expect(find.byIcon(Icons.grid_view_rounded), findsNothing);
    expect(find.byIcon(Icons.more_horiz_rounded), findsNothing);

    // Verify Settings icon
    expect(find.byIcon(Icons.settings_outlined), findsOneWidget);
  });

  testWidgets('SettingsScreen renders all required items', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthProvider()),
          ChangeNotifierProvider(create: (_) => NotificationsProvider()),
        ],
        child: const MaterialApp(
          home: SettingsScreen(),
        ),
      ),
    );

    // 1. My Profile
    expect(find.text('My Profile'), findsOneWidget);

    // 2. App Settings
    expect(find.text('App Settings'), findsOneWidget);

    // 3. Notifications
    expect(find.text('Notifications'), findsOneWidget);

    // 4. Change Password
    expect(find.text('Change Password'), findsOneWidget);

    // 5. Terms & Conditions
    expect(find.text('Terms & Conditions'), findsOneWidget);

    // 6. Privacy Policy
    expect(find.text('Privacy Policy'), findsOneWidget);

    // 7. App Version
    expect(find.text('App Version'), findsOneWidget);
    expect(find.text('v1.0.0 (Build 100)'), findsOneWidget);

    // 8. Logout
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('TermsAndConditionsScreen renders scrollable content and sections', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: TermsAndConditionsScreen(),
      ),
    );

    expect(find.text('Terms & Conditions'), findsWidgets);
    expect(find.text('Acceptance of Terms'), findsOneWidget);
    expect(find.text('Authorized Enterprise Use & User Accounts'), findsOneWidget);
    expect(find.text('WhatsApp Cloud API & Communication Policy'), findsOneWidget);
  });

  testWidgets('PrivacyPolicyScreen renders scrollable content and sections', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: PrivacyPolicyScreen(),
      ),
    );

    expect(find.text('Privacy Policy'), findsWidgets);
    expect(find.text('Information We Collect'), findsOneWidget);
    expect(find.text('How Information is Utilized'), findsOneWidget);
    expect(find.text('Role-Based Data Scoping'), findsOneWidget);
  });
}
