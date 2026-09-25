import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

/// Dummy UPI / unlock payments — no Razorpay, ₹0 gateway.
class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key, required this.state});
  final AppState state;

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  bool busy = false;
  String? err;
  Map<String, dynamic>? order;
  final codeCtrl = TextEditingController(text: 'DEMO-UNLOCK');

  @override
  void dispose() {
    codeCtrl.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    setState(() {
      busy = true;
      err = null;
    });
    try {
      final o = await widget.state.createPayment(amountInr: 99);
      setState(() => order = o);
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _confirm() async {
    final id = order?['payment_id']?.toString();
    if (id == null) return;
    setState(() {
      busy = true;
      err = null;
    });
    try {
      final r = await widget.state.confirmPayment(id);
      setState(() => order = {...?order, ...r});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unlocked — re-run Health Check for full detail')),
        );
      }
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _codeUnlock() async {
    setState(() {
      busy = true;
      err = null;
    });
    try {
      await widget.state.unlock(codeCtrl.text.trim());
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Code accepted — full intelligence unlocked')),
        );
      }
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final unlocked = widget.state.api.unlocked;
    return NxScaffold(
      title: 'Payments',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [NxNavy.navy800, NxNavy.surfaceElevated],
              ),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: NxNavy.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  unlocked ? 'UNLOCKED' : 'LOCKED · TEASER MODE',
                  style: TextStyle(
                    color: unlocked ? NxNavy.success : NxNavy.warning,
                    fontWeight: FontWeight.w800,
                    fontSize: 12,
                    letterSpacing: 0.6,
                  ),
                ),
                const SizedBox(height: 8),
                const Text('Full intelligence · ₹99', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                const Text(
                  'Dummy UPI only in this build — no real charge. Confirms unlock so you can test the paywall path on APK.',
                  style: TextStyle(color: NxNavy.textSecondary, height: 1.4, fontSize: 13),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const Text('What you get', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 10),
          _bullet('All ranked issues + full holdings detail'),
          _bullet('L2 trained flags + L3 style-overlap pairs'),
          _bullet('Re-run Health / Build without teaser cuts'),
          const SizedBox(height: 18),
          ElevatedButton(
            onPressed: busy ? null : _create,
            child: Text(busy && order == null ? 'Creating…' : 'Start dummy ₹99 UPI'),
          ),
          if (order != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: NxNavy.card,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: NxNavy.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Order ${order!['payment_id']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('Amount: ₹${order!['amount_inr'] ?? 99}', style: const TextStyle(color: NxNavy.textSecondary)),
                  Text('Status: ${order!['status']}', style: const TextStyle(color: NxNavy.textSecondary)),
                  Text('VPA (demo): ${order!['upi_vpa_demo'] ?? 'nxance@okaxis'}', style: const TextStyle(color: NxNavy.textSecondary)),
                  const SizedBox(height: 8),
                  Text(
                    '${order!['qr_note'] ?? 'Demo only — no real UPI charge.'}',
                    style: const TextStyle(color: NxNavy.warning, fontSize: 12, height: 1.35),
                  ),
                  if (order!['status'] == 'pending') ...[
                    const SizedBox(height: 12),
                    ElevatedButton(
                      onPressed: busy ? null : _confirm,
                      child: const Text('I paid — confirm (dummy)'),
                    ),
                  ],
                  if (order!['status'] == 'paid') ...[
                    const SizedBox(height: 8),
                    Text(
                      'Code: ${order!['unlock_code'] ?? 'NXANCE-PAID'}',
                      style: const TextStyle(color: NxNavy.success, fontWeight: FontWeight.w800),
                    ),
                  ],
                ],
              ),
            ),
          ],
          const SizedBox(height: 28),
          const Text('Or use unlock code', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 8),
          TextField(
            controller: codeCtrl,
            decoration: const InputDecoration(
              hintText: 'DEMO-UNLOCK',
              helperText: 'DEMO-UNLOCK · NXANCE-TEST · NXANCE-PAID',
            ),
            inputFormatters: [UpperCaseTextFormatter()],
          ),
          const SizedBox(height: 10),
          OutlinedButton(onPressed: busy ? null : _codeUnlock, child: const Text('Apply code')),
          if (err != null) ...[
            const SizedBox(height: 12),
            Text(err!, style: const TextStyle(color: NxNavy.danger, fontSize: 13)),
          ],
          const SizedBox(height: 20),
          const Text(
            'Not a real payment gateway. Production will wire Razorpay/UPI after paid users exist.',
            style: TextStyle(color: NxNavy.textMuted, fontSize: 11, height: 1.35),
          ),
        ],
      ),
    );
  }

  Widget _bullet(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('•  ', style: TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w800)),
            Expanded(child: Text(t, style: const TextStyle(color: NxNavy.textSecondary, height: 1.35))),
          ],
        ),
      );
}

class UpperCaseTextFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    return TextEditingValue(
      text: newValue.text.toUpperCase(),
      selection: newValue.selection,
    );
  }
}
