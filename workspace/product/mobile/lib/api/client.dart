import 'dart:convert';
import 'package:http/http.dart' as http;

/// Android emulator → host machine: 10.0.2.2
/// Real device → set LAN IP in Settings
class NxApi {
  NxApi({this.baseUrl = 'http://10.0.2.2:8000'});

  String baseUrl;
  String? token;
  bool unlocked = false;
  String? userName;
  String? userId;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null && token!.isNotEmpty) 'Authorization': 'Bearer $token',
      };

  void applySession(Map<String, dynamic>? session) {
    if (session == null) return;
    if (session['token'] != null) token = session['token'].toString();
    if (session['unlocked'] != null) unlocked = session['unlocked'] == true;
    if (session['name'] != null) userName = session['name'].toString();
    if (session['user_id'] != null) userId = session['user_id'].toString();
  }

  Future<Map<String, dynamic>> get(String path) async {
    final res = await http
        .get(Uri.parse('$baseUrl$path'), headers: _headers)
        .timeout(const Duration(seconds: 45));
    return _decode(res);
  }

  Future<Map<String, dynamic>> post(String path, [Map<String, dynamic>? body]) async {
    final res = await http
        .post(
          Uri.parse('$baseUrl$path'),
          headers: _headers,
          body: body == null ? null : jsonEncode(body),
        )
        .timeout(const Duration(seconds: 90));
    return _decode(res);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String fieldName,
    required String filename,
    required List<int> bytes,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    final req = http.MultipartRequest('POST', uri);
    if (token != null && token!.isNotEmpty) {
      req.headers['Authorization'] = 'Bearer $token';
    }
    req.files.add(http.MultipartFile.fromBytes(fieldName, bytes, filename: filename));
    final streamed = await req.send().timeout(const Duration(seconds: 120));
    final res = await http.Response.fromStream(streamed);
    return _decode(res);
  }

  Map<String, dynamic> _decode(http.Response res) {
    dynamic data;
    try {
      data = jsonDecode(res.body);
    } catch (_) {
      throw Exception(res.body.isEmpty ? 'Empty response (${res.statusCode})' : res.body);
    }
    if (res.statusCode >= 400) {
      final msg = data is Map ? (data['detail'] ?? data['message'] ?? res.body) : res.body;
      throw Exception(msg.toString());
    }
    final map = Map<String, dynamic>.from(data as Map);
    if (map['session'] is Map) {
      applySession(Map<String, dynamic>.from(map['session'] as Map));
    }
    // login/signup top-level token
    if (map['token'] != null) {
      applySession({
        'token': map['token'],
        'user_id': map['user_id'],
        'name': map['name'],
        'unlocked': map['unlocked'] ?? false,
      });
    }
    return map;
  }

  Future<Map<String, dynamic>> health() => get('/api/health');

  Future<Map<String, dynamic>> runDemo() => post('/api/demo/run');

  Future<Map<String, dynamic>> samplePortfolio() => get('/api/sample-portfolio');

  Future<Map<String, dynamic>> healthCheck({
    required List<Map<String, dynamic>> holdings,
    Map<String, dynamic>? questionnaire,
  }) =>
      post('/api/health-check', {
        'holdings': holdings,
        if (questionnaire != null) 'questionnaire': questionnaire,
      });

  Future<Map<String, dynamic>> construction(Map<String, dynamic> questionnaire) =>
      post('/api/construction', {'questionnaire': questionnaire});

  Future<Map<String, dynamic>> unlock(String code) =>
      post('/api/unlock', {'code': code});

  Future<Map<String, dynamic>> login({required String name, required String phone}) =>
      post('/api/login', {'name': name, 'phone': phone});

  Future<Map<String, dynamic>> signup({required String name, required String phone}) =>
      post('/api/signup', {'name': name, 'phone': phone});

  Future<Map<String, dynamic>> createPayment({double amountInr = 99}) =>
      post('/api/payments/create', {'amount_inr': amountInr, 'method': 'dummy_upi'});

  Future<Map<String, dynamic>> confirmPayment(String paymentId) =>
      post('/api/payments/confirm', {'payment_id': paymentId});

  Future<Map<String, dynamic>> uploadDocument({
    required String filename,
    required List<int> bytes,
  }) =>
      postMultipart('/api/ingest/document', fieldName: 'file', filename: filename, bytes: bytes);

  Future<Map<String, dynamic>> ingestFormats() => get('/api/ingest/formats');

  Future<Map<String, dynamic>> chat(String message, {String? reportId}) =>
      post('/api/chat', {
        'message': message,
        if (reportId != null) 'report_id': reportId,
      });

  Future<Map<String, dynamic>> trainingStatus() => get('/api/training/status');
}
