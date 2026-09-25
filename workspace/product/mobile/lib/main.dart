import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/build_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/health_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/payments_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/upload_screen.dart';
import 'state/app_state.dart';
import 'theme/navy.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  runApp(const NxanceApp());
}

class NxanceApp extends StatefulWidget {
  const NxanceApp({super.key});
  @override
  State<NxanceApp> createState() => _NxanceAppState();
}

class _NxanceAppState extends State<NxanceApp> {
  final state = AppState();
  int idx = 0;
  bool showLogin = true;

  @override
  void dispose() {
    state.dispose();
    super.dispose();
  }

  void _enterApp() => setState(() => showLogin = false);

  void _go(int i) => setState(() => idx = i);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Nxance',
      debugShowCheckedModeBanner: false,
      theme: NxNavy.theme(),
      home: ListenableBuilder(
        listenable: state,
        builder: (context, _) {
          if (showLogin) {
            return Scaffold(
              body: LoginScreen(state: state, onSuccess: _enterApp),
            );
          }

          // 5 primary tabs — Build & Ask reachable from Home / More
          final pages = [
            HomeScreen(
              state: state,
              onOpenHealth: () => _go(1),
              onOpenBuild: () => _go(3),
              onOpenUpload: () => _go(2),
              onOpenPay: () => _go(4),
              onOpenChat: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => Scaffold(appBar: AppBar(title: const Text('Ask Nxance')), body: ChatScreen(state: state))),
              ),
              onOpenSettings: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => Scaffold(appBar: AppBar(title: const Text('Settings')), body: SettingsScreen(state: state))),
              ),
            ),
            HealthScreen(state: state),
            UploadScreen(state: state, onAnalysed: () => _go(1)),
            BuildScreen(state: state),
            PaymentsScreen(state: state),
          ];
          return Scaffold(
            body: IndexedStack(index: idx, children: pages),
            bottomNavigationBar: BottomNavigationBar(
              currentIndex: idx,
              onTap: (i) => setState(() => idx = i),
              items: const [
                BottomNavigationBarItem(icon: Icon(Icons.home_rounded), label: 'Home'),
                BottomNavigationBarItem(icon: Icon(Icons.monitor_heart_rounded), label: 'Health'),
                BottomNavigationBarItem(icon: Icon(Icons.upload_file_rounded), label: 'Upload'),
                BottomNavigationBarItem(icon: Icon(Icons.pie_chart_rounded), label: 'Build'),
                BottomNavigationBarItem(icon: Icon(Icons.payments_rounded), label: 'Pay'),
              ],
            ),
          );
        },
      ),
    );
  }
}
