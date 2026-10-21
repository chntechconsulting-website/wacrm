import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/constants/app_theme.dart';
import 'core/widgets/loading_indicator.dart';
import 'core/widgets/pingo_mascot_widget.dart';
import 'features/activities/providers/activities_provider.dart';
import 'features/auth/presentation/landing_welcome_screen.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/providers/auth_provider.dart';
import 'features/calls/providers/calls_provider.dart';
import 'features/customers/providers/customers_provider.dart';
import 'features/dashboard/providers/dashboard_provider.dart';
import 'features/deals/providers/deals_provider.dart';
import 'features/field_visits/providers/field_visits_provider.dart';
import 'features/followups/providers/followups_provider.dart';
import 'features/leads/providers/leads_provider.dart';
import 'features/navigation/main_navigation_shell.dart';
import 'features/notifications/providers/notifications_provider.dart';
import 'features/quotations/providers/quotations_provider.dart';
import 'features/support/providers/support_provider.dart';

class WaCrmApp extends StatelessWidget {
  const WaCrmApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()..initAuth()),
        ChangeNotifierProvider(create: (_) => DashboardProvider()),
        ChangeNotifierProvider(create: (_) => LeadsProvider()),
        ChangeNotifierProvider(create: (_) => CustomersProvider()),
        ChangeNotifierProvider(create: (_) => FollowupsProvider()),
        ChangeNotifierProvider(create: (_) => FieldVisitsProvider()),
        ChangeNotifierProvider(create: (_) => ActivitiesProvider()),
        ChangeNotifierProvider(create: (_) => DealsProvider()),
        ChangeNotifierProvider(create: (_) => QuotationsProvider()),
        ChangeNotifierProvider(create: (_) => CallsProvider()),
        ChangeNotifierProvider(create: (_) => SupportProvider()),
        ChangeNotifierProvider(create: (_) => NotificationsProvider()),
      ],
      child: MaterialApp(
        title: 'WACRM Mobile',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        home: const AuthGate(),
      ),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final PageController _pageController = PageController();

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();

    switch (authProvider.status) {
      case AuthStatus.uninitialized:
      case AuthStatus.loading:
        if (authProvider.currentUser != null) {
          return const MainNavigationShell();
        }
        return const Scaffold(
          body: LoadingIndicator(
            message: 'Starting WACRM Mobile...',
            showMascot: true,
            mascotPose: PingoPoses.walk,
          ),
        );
      case AuthStatus.authenticated:
        return const MainNavigationShell();
      case AuthStatus.unauthenticated:
        return PageView(
          controller: _pageController,
          children: [
            LandingWelcomeScreen(
              onContinue: () {
                _pageController.animateToPage(
                  1,
                  duration: const Duration(milliseconds: 350),
                  curve: Curves.easeInOut,
                );
              },
            ),
            const LoginScreen(),
          ],
        );
    }
  }
}
