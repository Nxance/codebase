import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class HealthScreen extends StatefulWidget {
  const HealthScreen({super.key, required this.state});
  final AppState state;
  @override
  State<HealthScreen> createState() => _HealthScreenState();
}

class _HoldingRow {
  final name = TextEditingController();
  final value = TextEditingController();
  final invested = TextEditingController();
  String asset = 'mutual_fund';
  String plan = 'regular';
  void dispose() {
    name.dispose();
    value.dispose();
    invested.dispose();
  }
}

class _HealthScreenState extends State<HealthScreen> {
  final List<_HoldingRow> rows = [];
  final goal = TextEditingController(text: 'Wealth Creation');
  final target = TextEditingController(text: '5000000');
  final years = TextEditingController(text: '10');
  final sip = TextEditingController(text: '10000');
  String risk = 'moderate';
  String? unlockCode;
  final unlockCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    rows.add(_HoldingRow());
  }

  @override
  void dispose() {
    for (final r in rows) {
      r.dispose();
    }
    goal.dispose();
    target.dispose();
    years.dispose();
    sip.dispose();
    unlockCtrl.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _collect() {
    final out = <Map<String, dynamic>>[];
    for (final r in rows) {
      final n = r.name.text.trim();
      final v = double.tryParse(r.value.text) ?? 0;
      final i = double.tryParse(r.invested.text) ?? v;
      if (n.isEmpty || (v <= 0 && i <= 0)) continue;
      out.add({
        'name': n,
        'current_value': v > 0 ? v : i,
        'invested_amount': i > 0 ? i : v,
        'asset_class': r.asset,
        'plan_type': r.plan,
        'purchase_date': '2021-01-01',
      });
    }
    return out;
  }

  Future<void> _loadSampleRows() async {
    try {
      final data = await widget.state.api.samplePortfolio();
      final list = (data['holdings'] as List?) ?? [];
      setState(() {
        for (final r in rows) {
          r.dispose();
        }
        rows
          ..clear()
          ..addAll(list.map((h) {
            final row = _HoldingRow();
            row.name.text = '${h['name'] ?? ''}';
            row.value.text = '${h['current_value'] ?? ''}';
            row.invested.text = '${h['invested_amount'] ?? ''}';
            row.asset = '${h['asset_class'] ?? 'mutual_fund'}';
            row.plan = '${h['plan_type'] ?? 'regular'}';
            return row;
          }));
        if (rows.isEmpty) rows.add(_HoldingRow());
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Sample rows loaded — replace with yours before relying on numbers')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  Future<void> _analyse() async {
    final holdings = _collect();
    if (holdings.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Add at least one holding — we never invent a loss on empty data')));
      return;
    }
    try {
      await widget.state.analyseHoldings(
        holdings: holdings,
        questionnaire: {
          'goal': goal.text,
          'target_amount': double.tryParse(target.text) ?? 0,
          'years': double.tryParse(years.text) ?? 10,
          'monthly_sip': double.tryParse(sip.text) ?? 0,
          'risk': risk,
          'risk_response': risk,
        },
      );
      setState(() {});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final Map<String, dynamic>? report = widget.state.lastHealth;
    final story = report == null ? null : report['story'] as Map<String, dynamic>?;
    final isSample = report != null && report['is_sample'] == true;
    final issues = report == null ? <dynamic>[] : ((report['issues'] as List?) ?? []);

    return NxScaffold(
      title: 'Health Check',
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
        children: [
          const Text('Holdings first · questionnaire second', style: TextStyle(color: NxNavy.textSecondary, fontSize: 13)),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(onPressed: widget.state.busy ? null : () async {
                  try {
                    await widget.state.runDemo();
                    setState(() {});
                  } catch (e) {
                    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                  }
                }, child: const Text('Sample demo')),
              ),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: _loadSampleRows, child: const Text('Load sample rows'))),
            ],
          ),
          const SizedBox(height: 14),
          ...rows.asMap().entries.map((e) {
            final i = e.key;
            final r = e.value;
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: NxNavy.card, borderRadius: BorderRadius.circular(14), border: Border.all(color: NxNavy.border)),
              child: Column(
                children: [
                  TextField(controller: r.name, decoration: const InputDecoration(labelText: 'Name (fund / stock / FD)')),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(child: TextField(controller: r.value, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Current ₹'))),
                    const SizedBox(width: 8),
                    Expanded(child: TextField(controller: r.invested, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Invested ₹'))),
                  ]),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        // ignore: deprecated_member_use
                        value: r.asset,
                        dropdownColor: NxNavy.card,
                        items: const [
                          DropdownMenuItem(value: 'mutual_fund', child: Text('MF')),
                          DropdownMenuItem(value: 'stock', child: Text('Stock')),
                          DropdownMenuItem(value: 'fd', child: Text('FD')),
                        ],
                        onChanged: (v) => setState(() => r.asset = v ?? 'mutual_fund'),
                        decoration: const InputDecoration(labelText: 'Type'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        // ignore: deprecated_member_use
                        value: r.plan,
                        dropdownColor: NxNavy.card,
                        items: const [
                          DropdownMenuItem(value: 'regular', child: Text('Regular')),
                          DropdownMenuItem(value: 'direct', child: Text('Direct')),
                        ],
                        onChanged: (v) => setState(() => r.plan = v ?? 'regular'),
                        decoration: const InputDecoration(labelText: 'Plan'),
                      ),
                    ),
                    IconButton(
                      onPressed: rows.length == 1
                          ? null
                          : () => setState(() {
                                rows.removeAt(i).dispose();
                              }),
                      icon: const Icon(Icons.close, color: NxNavy.textMuted),
                    ),
                  ]),
                ],
              ),
            );
          }),
          TextButton.icon(
            onPressed: () => setState(() => rows.add(_HoldingRow())),
            icon: const Icon(Icons.add, color: NxNavy.accent),
            label: const Text('Add holding', style: TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(height: 8),
          const Text('About this portfolio', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
          const SizedBox(height: 8),
          TextField(controller: goal, decoration: const InputDecoration(labelText: 'Goal')),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: target, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Target ₹'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: years, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Years'))),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: sip, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Monthly SIP ₹'))),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<String>(
                // ignore: deprecated_member_use
                value: risk,
                dropdownColor: NxNavy.card,
                items: const [
                  DropdownMenuItem(value: 'conservative', child: Text('Conservative')),
                  DropdownMenuItem(value: 'moderate', child: Text('Moderate')),
                  DropdownMenuItem(value: 'aggressive', child: Text('Aggressive')),
                ],
                onChanged: (v) => setState(() => risk = v ?? 'moderate'),
                decoration: const InputDecoration(labelText: 'Risk'),
              ),
            ),
          ]),
          const SizedBox(height: 14),
          ElevatedButton(
            onPressed: widget.state.busy ? null : _analyse,
            child: Text(widget.state.busy ? 'Running engines…' : 'Run diagnosis'),
          ),
          if (report != null) ...[
            const SizedBox(height: 20),
            if (isSample) ...[
              SampleBanner(title: story?['banner']?['title']?.toString() ?? 'Illustrative sample — not your portfolio'),
              const SizedBox(height: 10),
            ],
            ScoreHeader(
              score: report['score'] ?? '—',
              grade: '${report['grade'] ?? ''} · ${report['grade_label'] ?? ''}',
              headline: story?['headline']?.toString() ?? report['teaser_summary']?.toString() ?? '',
            ),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(child: KpiTile(label: story?['hero_metric']?['label']?.toString() ?? 'Avoidable', value: story?['hero_metric']?['display']?.toString() ?? '—', danger: true)),
              const SizedBox(width: 8),
              Expanded(child: KpiTile(label: 'XIRR', value: report['portfolio_xirr'] != null ? '${report['portfolio_xirr']}%' : '—')),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: KpiTile(label: 'TER leak', value: '₹${inr(report['ter_waste_annual_rs'])}')),
              const SizedBox(width: 8),
              Expanded(child: KpiTile(label: 'Overlap', value: '₹${inr(report['overlap_waste_annual_rs'])}')),
            ]),
            const SizedBox(height: 14),
            const Text('Findings', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            ...issues.asMap().entries.map((e) => IssueCard(issue: Map<String, dynamic>.from(e.value as Map), index: e.key)),
            if (report['locked_issue_count'] != null && (report['locked_issue_count'] as num) > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Text('${report['locked_issue_count']} more issues locked — unlock for full list', style: const TextStyle(color: NxNavy.textMuted, fontSize: 12)),
              ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [NxNavy.navy950, NxNavy.navy800]),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: NxNavy.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Unlock full report · ₹99', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                  const SizedBox(height: 6),
                  const Text('Test codes: DEMO-UNLOCK · NXANCE-TEST', style: TextStyle(color: NxNavy.textSecondary, fontSize: 12)),
                  const SizedBox(height: 10),
                  TextField(controller: unlockCtrl, decoration: const InputDecoration(hintText: 'Enter code')),
                  const SizedBox(height: 10),
                  ElevatedButton(
                    onPressed: widget.state.busy
                        ? null
                        : () async {
                            try {
                              await widget.state.unlock(unlockCtrl.text.trim());
                              if (mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Unlocked — re-run diagnosis for full output')));
                              }
                            } catch (e) {
                              if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                            }
                          },
                    child: const Text('Unlock'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Stack: ${((report['intelligence_stack'] as Map?)?['layers'] as List?)?.join(' → ') ?? '—'}',
              style: const TextStyle(color: NxNavy.textMuted, fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }
}
