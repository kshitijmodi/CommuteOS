import 'package:flutter/material.dart';

import '../account/account_screen.dart';
import '../chat/chat_screen.dart';
import '../favorites/favorites_screen.dart';
import '../transit/station_search_screen.dart';

/// Bottom-nav shell hosting the app's four top-level destinations. This
/// replaces the old appbar-icon navigation (search/account icons on the
/// favorites screen) now that the app has enough distinct sections (browse,
/// search, chat, account/preferences/recommendations) to warrant persistent
/// bottom nav rather than icons bolted onto one screen's appbar.
///
/// Chat gets its own top-level tab rather than living under Account,
/// because Chat AI's stateless tier deliberately needs no login (see
/// backend/app/chat_ai.py) - nesting it under the account tab would wrongly
/// imply it's gated the way the recommendation/preferences screens are.
///
/// Each tab keeps its own Navigator so pushing a detail screen (e.g.
/// arrivals) doesn't hide the bottom nav or lose the other tabs' state.
class RootShell extends StatefulWidget {
  const RootShell({super.key});

  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int _index = 0;

  final _navigatorKeys = [
    GlobalKey<NavigatorState>(),
    GlobalKey<NavigatorState>(),
    GlobalKey<NavigatorState>(),
    GlobalKey<NavigatorState>(),
  ];

  static const _tabs = [
    (icon: Icons.star_border_rounded, selectedIcon: Icons.star_rounded, label: 'Favorites'),
    (icon: Icons.search_rounded, selectedIcon: Icons.search_rounded, label: 'Search'),
    (icon: Icons.chat_bubble_outline_rounded, selectedIcon: Icons.chat_bubble_rounded, label: 'Chat'),
    (icon: Icons.person_outline_rounded, selectedIcon: Icons.person_rounded, label: 'Account'),
  ];

  Widget _buildTab(int index, Widget child) {
    return Navigator(
      key: _navigatorKeys[index],
      onGenerateRoute: (settings) =>
          MaterialPageRoute(builder: (_) => child, settings: settings),
    );
  }

  Future<bool> _onWillPop() async {
    final navigator = _navigatorKeys[_index].currentState!;
    if (navigator.canPop()) {
      navigator.pop();
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _onWillPop()) {
          if (context.mounted) Navigator.of(context).maybePop();
        }
      },
      child: Scaffold(
        body: IndexedStack(
          index: _index,
          children: [
            _buildTab(0, const FavoritesScreen()),
            _buildTab(1, const StationSearchScreen()),
            _buildTab(2, const ChatScreen()),
            _buildTab(3, const AccountScreen()),
          ],
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (i) {
            if (i == _index) {
              _navigatorKeys[i].currentState?.popUntil((r) => r.isFirst);
            } else {
              setState(() => _index = i);
            }
          },
          destinations: [
            for (final tab in _tabs)
              NavigationDestination(
                icon: Icon(tab.icon),
                selectedIcon: Icon(tab.selectedIcon),
                label: tab.label,
              ),
          ],
        ),
      ),
    );
  }
}
