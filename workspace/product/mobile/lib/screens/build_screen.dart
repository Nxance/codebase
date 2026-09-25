import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class BuildScreen extends StatefulWidget {
  const BuildScreen({super.key, required this.state});
  final AppState state;
  @override
  State<BuildScreen> createState() => _BuildScreenState();
}

class _BuildScreenState extends State<BuildScreen> {
  double sip = 15000;
  double years = 12;
  double lump = 100000;
  double target = 5000000;
  String risk = 'moderate';
  String goal = 'Wealth Creation';

  Future<void> _run() async {
    try {
      await widget.state.buildPortfolio({
        'goal': goal,
        'target_amount': target,
        'years': years,
        'monthly_sip': sip,
        'lumpsum': lump,
        'risk': risk,
        'risk_response': risk,
      });
      setState(() {});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.state.lastConstruction;
    final alloc = r?['allocation']?['allocation_pct'] as Map<String, dynamic>?;
    final instruments = (r?['instruments'] as List?) ?? [];
    final unlocked = r?['unlocked'] == true;

    return NxScaffold(
      title: 'Construction',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
        children: [
          const Text('Questions first · optimiser designs · you execute', style: TextStyle(color: NxNavy.textSecondary, fontSize: 13)),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            // ignore: deprecated_member_use
            value: goal,
            dropdownColor: NxNavy.card,
            items: const [
              DropdownMenuItem(value: 'Wealth Creation', child: Text('Wealth Creation')),
              DropdownMenuItem(value: 'Retirement', child: Text('Retirement')),
              DropdownMenuItem(value: 'Buy a House', child: Text('Buy a House')),
              DropdownMenuItem(value: 'Child Education', child: Text('Child Education')),
            ],
            onChanged: (v) => setState(() => goal = v ?? goal),
            decoration: const InputDecoration(labelText: 'Goal'),
          ),
          const SizedBox(height: 12),
          Text('Monthly SIP  ₹${sip.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w700)),
          Slider(value: sip, min: 2000, max: 100000, divisions: 49, activeColor: NxNavy.accent, onChanged: (v) => setState(() => sip = v)),
          Text('Years  ${years.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w700)),
          Slider(value: years, min: 3, max: 30, divisions: 27, activeColor: NxNavy.accent, onChanged: (v) => setState(() => years = v)),
          Text('Lump sum  ₹${lump.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w700)),
          Slider(value: lump, min: 0, max: 2000000, divisions: 40, activeColor: NxNavy.accent, onChanged: (v) => setState(() => lump = v)),
          Text('Target  ₹${target.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w700)),
          Slider(value: target, min: 500000, max: 20000000, divisions: 39, activeColor: NxNavy.accent, onChanged: (v) => setState(() => target = v)),
          DropdownButtonFormField<String>(
            // ignore: deprecated_member_use
            value: risk,
            dropdownColor: NxNavy.card,
            items: const [
              DropdownMenuItem(value: 'conservative', child: Text('Conservative')),
              DropdownMenuItem(value: 'moderate', child: Text('Moderate')),
              DropdownMenuItem(value: 'aggressive', child: Text('Aggressive')),
            ],
            onChanged: (v) => setState(() => risk = v ?? risk),
            decoration: const InputDecoration(labelText: 'Risk'),
          ),
          const SizedBox(height: 14),
          ElevatedButton(onPressed: widget.state.busy ? null : _run, child: Text(widget.state.busy ? 'Optimising…' : 'Design portfolio')),
          if (alloc != null) ...[
            const SizedBox(height: 18),
            Text(r?['story']?['headline']?.toString() ?? r?['teaser_summary']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w700, height: 1.35)),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: KpiTile(label: 'Equity', value: '${alloc['equity']}%')),
              const SizedBox(width: 8),
              Expanded(child: KpiTile(label: 'Debt MF', value: '${alloc['debt_mf']}%')),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: KpiTile(label: 'FD', value: '${alloc['fd']}%')),
              const SizedBox(width: 8),
              Expanded(child: KpiTile(label: 'Expected', value: '${r?['expected_return_pct']}%/yr')),
            ]),
            const SizedBox(height: 14),
            Text(unlocked ? 'Instruments' : 'Instruments (names may be locked)', style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            ...instruments.map((raw) {
              final i = Map<String, dynamic>.from(raw as Map);
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: NxNavy.card, borderRadius: BorderRadius.circular(12), border: Border.all(color: NxNavy.border)),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${i['name'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w700)),
                        Text('${i['type'] ?? ''} · FIT ${i['fit_score'] ?? '—'}', style: const TextStyle(color: NxNavy.textMuted, fontSize: 12)),
                      ]),
                    ),
                    Text('${i['allocation_pct'] ?? '—'}%', style: const TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w800)),
                  ],
                ),
              );
            }),
            if (r?['projection'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  'Projection range ₹${inr(r!['projection']['conservative_rs'])} – ₹${inr(r['projection']['base_rs'])} (illustrative)',
                  style: const TextStyle(color: NxNavy.textMuted, fontSize: 12),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
