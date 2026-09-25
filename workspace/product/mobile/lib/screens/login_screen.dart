import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.state, this.onSuccess});
  final AppState state;
  final VoidCallback? onSuccess;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final name = TextEditingController();
  final phone = TextEditingController();
  bool busy = false;
  String? err;

  @override
  void dispose() {
    name.dispose();
    phone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final n = name.text.trim();
    final p = phone.text.trim();
    if (n.isEmpty || p.length < 8) {
      setState(() => err = 'Enter name and a valid phone (min 8 digits)');
      return;
    }
    setState(() {
      busy = true;
      err = null;
    });
    try {
      await widget.state.login(name: n, phone: p);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Welcome, ${widget.state.userName ?? n}')),
        );
        widget.onSuccess?.call();
      }
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _guest() async {
    setState(() {
      busy = true;
      err = null;
    });
    try {
      await widget.state.continueAsGuest();
      widget.onSuccess?.call();
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return NxScaffold(
      title: 'Sign in',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: NxNavy.card,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: NxNavy.border),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Demo auth · no OTP', style: TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w800, fontSize: 12)),
                SizedBox(height: 8),
                Text(
                  'Free MBP login — name + phone creates a session. No SMS cost. Unlock via dummy payments or DEMO-UNLOCK.',
                  style: TextStyle(color: NxNavy.textSecondary, height: 1.4, fontSize: 13),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          const Text('Your name', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          TextField(
            controller: name,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(hintText: 'e.g. Priya Sharma'),
          ),
          const SizedBox(height: 14),
          const Text('Phone', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          TextField(
            controller: phone,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(hintText: '10-digit mobile'),
          ),
          if (err != null) ...[
            const SizedBox(height: 12),
            Text(err!, style: const TextStyle(color: NxNavy.danger, fontSize: 13)),
          ],
          const SizedBox(height: 18),
          ElevatedButton(
            onPressed: busy ? null : _submit,
            child: Text(busy ? 'Signing in…' : 'Continue'),
          ),
          const SizedBox(height: 10),
          OutlinedButton(
            onPressed: busy ? null : _guest,
            child: const Text('Continue as guest'),
          ),
          const SizedBox(height: 24),
          const Text(
            'Suggestion only · Not SEBI investment advice · ₹0 auth stack',
            style: TextStyle(color: NxNavy.textMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
