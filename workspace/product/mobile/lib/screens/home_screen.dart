import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.state,
    required this.onOpenHealth,
    required this.onOpenBuild,
    this.onOpenUpload,
    this.onOpenPay,
    this.onOpenChat,
    this.onOpenSettings,
  });
  final AppState state;
  final VoidCallback onOpenHealth;
  final VoidCallback onOpenBuild;
  final VoidCallback? onOpenUpload;
  final VoidCallback? onOpenPay;
  final VoidCallback? onOpenChat;
  final VoidCallback? onOpenSettings;

  @override
  Widget build(BuildContext context) {
    return NxScaffold(
      title: 'nxance',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: NxNavy.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(999),
            ),
            child: const Text('INDIA · SUGGESTION ONLY', style: TextStyle(color: NxNavy.accent, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
          ),
          const SizedBox(height: 18),
          const Text(
            'Know if your money\nis actually working',
            style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, height: 1.12, letterSpacing: -0.6),
          ),
          const SizedBox(height: 12),
          const Text(
            'Diagnose MF, stocks & FDs with exact ₹ impact. Quant measures, ML scores, deep embeddings — language only explains.',
            style: TextStyle(color: NxNavy.textSecondary, height: 1.45, fontSize: 15),
          ),
          const SizedBox(height: 22),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [NxNavy.surfaceElevated, NxNavy.navy800],
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: NxNavy.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('NO DATA → NO PERSONAL LOSS', style: TextStyle(color: NxNavy.accent, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
                const SizedBox(height: 8),
                const Text('Navy Android companion', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                const Text('Sample demos are tagged. Unlock codes work after UPI. Engines never invent holdings.', style: TextStyle(color: NxNavy.textSecondary, fontSize: 13, height: 1.4)),
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(child: _pill('L1 Quant')),
                  const SizedBox(width: 8),
                  Expanded(child: _pill('L2+L3 ML/DL')),
                ]),
              ],
            ),
          ),
          const SizedBox(height: 18),
          if (state.userName != null) ...[
            Text(
              'Hi, ${state.userName}${state.api.unlocked ? ' · Unlocked' : ''}',
              style: const TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w700, fontSize: 13),
            ),
            const SizedBox(height: 12),
          ],
          ElevatedButton(
            onPressed: state.busy
                ? null
                : () async {
                    try {
                      await state.runDemo();
                      onOpenHealth();
                    } catch (_) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(state.statusMessage ?? 'Error')));
                      }
                    }
                  },
            child: Text(state.busy ? 'Working…' : 'Run labelled sample demo'),
          ),
          const SizedBox(height: 10),
          OutlinedButton(onPressed: onOpenHealth, child: const Text('Health Check — my holdings')),
          const SizedBox(height: 10),
          OutlinedButton(
            onPressed: onOpenUpload,
            child: const Text('Upload CAS / PDF / Excel / screenshot'),
          ),
          const SizedBox(height: 10),
          OutlinedButton(onPressed: onOpenBuild, child: const Text('Build a portfolio')),
          const SizedBox(height: 10),
          OutlinedButton(
            onPressed: onOpenPay,
            child: Text(state.api.unlocked ? 'Payments · unlocked' : 'Unlock · dummy ₹99'),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(onPressed: onOpenChat, child: const Text('Ask Nxance')),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton(onPressed: onOpenSettings, child: const Text('Settings')),
              ),
            ],
          ),
          if (state.statusMessage != null) ...[
            const SizedBox(height: 16),
            Text(state.statusMessage!, style: const TextStyle(color: NxNavy.textMuted, fontSize: 12)),
          ],
        ],
      ),
    );
  }

  Widget _pill(String t) => Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(color: NxNavy.card, borderRadius: BorderRadius.circular(10), border: Border.all(color: NxNavy.border)),
        alignment: Alignment.center,
        child: Text(t, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: NxNavy.textSecondary)),
      );
}
