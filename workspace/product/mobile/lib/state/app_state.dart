import 'package:flutter/foundation.dart';
import '../api/client.dart';

/// Default API host by platform:
/// - Android emulator → 10.0.2.2
/// - iOS simulator / macOS / Chrome → 127.0.0.1
String defaultApiBase() {
  if (kIsWeb) return 'http://127.0.0.1:8000';
  switch (defaultTargetPlatform) {
    case TargetPlatform.android:
      return 'http://10.0.2.2:8000';
    default:
      return 'http://127.0.0.1:8000';
  }
}

class AppState extends ChangeNotifier {
  AppState({String? baseUrl}) {
    api = NxApi(baseUrl: baseUrl ?? defaultApiBase());
  }

  late NxApi api;
  Map<String, dynamic>? lastHealth;
  Map<String, dynamic>? lastConstruction;
  Map<String, dynamic>? lastUpload;
  String? lastReportId;
  String? statusMessage;
  bool busy = false;
  bool guestMode = true;

  String? get userName => api.userName;
  bool get isLoggedIn => api.token != null && api.token!.isNotEmpty;

  void setBaseUrl(String url) {
    api.baseUrl = url.trim().replaceAll(RegExp(r'/$'), '');
    notifyListeners();
  }

  void _setBusy(bool v, [String? msg]) {
    busy = v;
    statusMessage = msg;
    notifyListeners();
  }

  Future<void> login({required String name, required String phone}) async {
    _setBusy(true, 'Signing in…');
    try {
      final r = await api.login(name: name, phone: phone);
      guestMode = false;
      statusMessage = r['message']?.toString() ?? 'Signed in';
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> continueAsGuest() async {
    guestMode = true;
    // Demo run creates a guest session when needed; clear name only
    api.userName = 'Guest';
    statusMessage = 'Continuing as guest';
    notifyListeners();
  }

  Future<void> runDemo() async {
    _setBusy(true, 'Running sample…');
    try {
      lastHealth = await api.runDemo();
      lastReportId = lastHealth?['report_id']?.toString();
      statusMessage = 'Sample ready (not your portfolio)';
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> analyseHoldings({
    required List<Map<String, dynamic>> holdings,
    required Map<String, dynamic> questionnaire,
  }) async {
    _setBusy(true, 'Analysing…');
    try {
      lastHealth = await api.healthCheck(holdings: holdings, questionnaire: questionnaire);
      lastReportId = lastHealth?['report_id']?.toString();
      statusMessage = 'Analysis complete';
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> buildPortfolio(Map<String, dynamic> questionnaire) async {
    _setBusy(true, 'Designing…');
    try {
      lastConstruction = await api.construction(questionnaire);
      lastReportId = lastConstruction?['report_id']?.toString() ?? lastReportId;
      statusMessage = 'Portfolio designed';
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> unlock(String code) async {
    _setBusy(true, 'Unlocking…');
    try {
      await api.unlock(code);
      statusMessage = 'Unlocked — re-run for full detail';
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> createPayment({double amountInr = 99}) async {
    _setBusy(true, 'Creating payment…');
    try {
      final r = await api.createPayment(amountInr: amountInr);
      statusMessage = 'Dummy order created';
      return r;
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> confirmPayment(String paymentId) async {
    _setBusy(true, 'Confirming…');
    try {
      final r = await api.confirmPayment(paymentId);
      statusMessage = 'Payment confirmed — unlocked';
      return r;
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> uploadDocument({
    required String filename,
    required List<int> bytes,
  }) async {
    _setBusy(true, 'Parsing document…');
    try {
      lastUpload = await api.uploadDocument(filename: filename, bytes: bytes);
      statusMessage = 'Parsed ${lastUpload?['count'] ?? 0} holdings';
      return lastUpload!;
    } catch (e) {
      statusMessage = e.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }
}
