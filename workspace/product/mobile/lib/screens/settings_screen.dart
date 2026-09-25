import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.state});
  final AppState state;
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController url;
  Map<String, dynamic>? status;
  String? err;

  @override
  void initState() {
    super.initState();
    url = TextEditingController(text: widget.state.api.baseUrl);
  }

  @override
  void dispose() {
    url.dispose();
    super.dispose();
  }

  Future<void> _ping() async {
    setState(() {
      err = null;
      status = null;
    });
    try {
      widget.state.setBaseUrl(url.text);
      final h = await widget.state.api.health();
      final t = await widget.state.api.trainingStatus();
      setState(() => status = {'health': h, 'training': t});
    } catch (e) {
      setState(() => err = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return NxScaffold(
      title: 'Settings',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
        children: [
          const Text('API base URL', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          TextField(
            controller: url,
            decoration: const InputDecoration(
              hintText: 'http://10.0.2.2:8000',
              helperText: 'Emulator: 10.0.2.2 · Device: your Mac LAN IP',
            ),
          ),
          const SizedBox(height: 12),
          ElevatedButton(onPressed: _ping, child: const Text('Save & test connection')),
          if (err != null) ...[
            const SizedBox(height: 12),
            Text(err!, style: const TextStyle(color: NxNavy.danger)),
          ],
          if (status != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: NxNavy.card, borderRadius: BorderRadius.circular(14), border: Border.all(color: NxNavy.border)),
              child: Text(
                'Health: ${status!['health']}\n\nTraining: ${status!['training']}',
                style: const TextStyle(fontSize: 11, color: NxNavy.textSecondary, height: 1.35, fontFamily: 'monospace'),
              ),
            ),
          ],
          const SizedBox(height: 24),
          const Text('Session', style: TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Text('User: ${widget.state.userName ?? 'Guest'}', style: const TextStyle(color: NxNavy.textSecondary)),
          Text('Token: ${widget.state.api.token != null ? 'set' : 'none'}', style: const TextStyle(color: NxNavy.textSecondary)),
          Text('Unlocked: ${widget.state.api.unlocked}', style: const TextStyle(color: NxNavy.textSecondary)),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: () {
              widget.state.api.token = null;
              widget.state.api.unlocked = false;
              widget.state.api.userName = null;
              widget.state.api.userId = null;
              widget.state.guestMode = true;
              widget.state.statusMessage = 'Signed out';
              widget.state.notifyListeners();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Signed out — restart app to see login again')),
                );
              }
            },
            child: const Text('Sign out'),
          ),
          const SizedBox(height: 20),
          const Text('Nxance · Ohshn Intelligence · Palampur HP', style: TextStyle(color: NxNavy.textMuted, fontSize: 12)),
          const Text('Suggestion only · Not SEBI investment advice', style: TextStyle(color: NxNavy.textMuted, fontSize: 12)),
        ],
      ),
    );
  }
}
