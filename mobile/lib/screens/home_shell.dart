import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../services/auth_service.dart';
import '../services/location_service.dart';
import '../theme/app_theme.dart';
import '../widgets/system_mode_banner.dart';
import 'home_dashboard_screen.dart';
import 'sos_screen.dart';
import 'weather_screen.dart';
import 'market_screen.dart';
import 'schemes_screen.dart';
import 'family_screen.dart';

/// Bottom-nav shell. Tabs adapt to role: a fisherman gets the SOS tab
/// front and center; a family account gets the Family dashboard instead,
/// since SOS-triggering isn't something they do.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    if (AuthService.instance.currentUser?.isFisherman == true) {
      // Offline-first GPS capture begins the moment a fisherman is in the
      // app, not only when they open the map - that's what makes the trail
      // available when SOS or family tracking needs it later.
      LocationService.instance.requestPermissionAndStart();
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final isFisherman = AuthService.instance.currentUser?.isFisherman ?? true;

    final fishermanTabs = [
      (const HomeDashboardScreen(), Icons.home_outlined, Icons.home, t.navHome),
      (const SosScreen(), Icons.sos_outlined, Icons.sos, t.navSos),
      (const WeatherScreen(), Icons.cloud_outlined, Icons.cloud, t.navWeather),
      (const MarketScreen(), Icons.storefront_outlined, Icons.storefront, t.navMarket),
      (const SchemesScreen(), Icons.account_balance_outlined, Icons.account_balance, t.navSchemes),
    ];

    final familyTabs = [
      (const FamilyScreen(), Icons.family_restroom_outlined, Icons.family_restroom, t.navFamily),
      (const WeatherScreen(), Icons.cloud_outlined, Icons.cloud, t.navWeather),
      (const MarketScreen(), Icons.storefront_outlined, Icons.storefront, t.navMarket),
      (const SchemesScreen(), Icons.account_balance_outlined, Icons.account_balance, t.navSchemes),
    ];

    final tabs = isFisherman ? fishermanTabs : familyTabs;

    return Scaffold(
      body: Column(
        children: [
          const SystemModeBanner(),
          Expanded(
            child: IndexedStack(
              index: _index,
              children: tabs.map((tab) => tab.$1).toList(),
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        backgroundColor: Colors.white,
        indicatorColor: AppColors.deepSea.withOpacity(0.12),
        destinations: tabs
            .map((tab) => NavigationDestination(icon: Icon(tab.$2), selectedIcon: Icon(tab.$3, color: AppColors.deepSea), label: tab.$4))
            .toList(),
      ),
    );
  }
}
