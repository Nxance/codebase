import 'package:flutter/material.dart';
import '../theme/navy.dart';

class NxScaffold extends StatelessWidget {
  const NxScaffold({super.key, required this.title, required this.child, this.actions});
  final String title;
  final Widget child;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 12, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -0.4)),
                ),
                ...?actions,
              ],
            ),
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class SampleBanner extends StatelessWidget {
  const SampleBanner({super.key, this.title = 'Illustrative sample — not your portfolio'});
  final String title;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: NxNavy.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: NxNavy.warning.withValues(alpha: 0.35)),
      ),
      child: Text(title, style: const TextStyle(color: NxNavy.warning, fontWeight: FontWeight.w700, fontSize: 13)),
    );
  }
}

class KpiTile extends StatelessWidget {
  const KpiTile({super.key, required this.label, required this.value, this.danger = false});
  final String label;
  final String value;
  final bool danger;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: NxNavy.surfaceElevated,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: NxNavy.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: NxNavy.textMuted, fontSize: 11, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: danger ? NxNavy.danger : NxNavy.textPrimary)),
        ],
      ),
    );
  }
}

class ScoreHeader extends StatelessWidget {
  const ScoreHeader({super.key, required this.score, required this.grade, required this.headline});
  final dynamic score;
  final String grade;
  final String headline;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: NxNavy.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: NxNavy.border),
      ),
      child: Row(
        children: [
          Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: NxNavy.accent, width: 3),
              gradient: LinearGradient(colors: [NxNavy.navy700.withValues(alpha: 0.5), NxNavy.surface]),
            ),
            alignment: Alignment.center,
            child: Text('$score', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(grade, style: const TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w700, fontSize: 12)),
                const SizedBox(height: 6),
                Text(headline, style: const TextStyle(fontWeight: FontWeight.w600, height: 1.35, fontSize: 14)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class IssueCard extends StatelessWidget {
  const IssueCard({super.key, required this.issue, required this.index});
  final Map issue;
  final int index;
  @override
  Widget build(BuildContext context) {
    final sev = (issue['severity'] ?? 'medium').toString();
    final color = sev == 'high' || sev == 'critical' ? NxNavy.danger : sev == 'medium' ? NxNavy.warning : NxNavy.accent;
    final cost = issue['annual_cost_rs'];
    final costStr = cost != null && cost is num && cost > 0 ? '₹${cost.toStringAsFixed(0)}/yr' : '—';
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: NxNavy.card,
        borderRadius: BorderRadius.circular(14),
        border: Border(left: BorderSide(color: color, width: 3), top: const BorderSide(color: NxNavy.border), right: const BorderSide(color: NxNavy.border), bottom: const BorderSide(color: NxNavy.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('ISSUE ${index + 1} · ${sev.toUpperCase()}', style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.4)),
              const Spacer(),
              Text(costStr, style: const TextStyle(color: NxNavy.danger, fontWeight: FontWeight.w800, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 6),
          Text('${issue['title'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          const SizedBox(height: 4),
          Text('${issue['description'] ?? ''}', style: const TextStyle(color: NxNavy.textSecondary, fontSize: 13, height: 1.35)),
          if (issue['fix'] != null) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: NxNavy.accent.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
              child: Text('Fix → ${issue['fix']}', style: const TextStyle(color: NxNavy.accent, fontSize: 12.5, fontWeight: FontWeight.w600)),
            ),
          ],
        ],
      ),
    );
  }
}

String inr(dynamic n) {
  if (n == null) return '—';
  final v = n is num ? n : num.tryParse(n.toString());
  if (v == null) return '—';
  return v.toStringAsFixed(v == v.roundToDouble() ? 0 : 2);
}
