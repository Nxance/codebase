import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

/// CAS / statement / screenshot / spreadsheet upload space.
class UploadScreen extends StatefulWidget {
  const UploadScreen({
    super.key,
    required this.state,
    this.onAnalysed,
  });
  final AppState state;
  final VoidCallback? onAnalysed;

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  bool busy = false;
  String? err;
  Map<String, dynamic>? result;
  String? fileLabel;

  Future<void> _pick() async {
    setState(() {
      err = null;
    });
    final pick = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const [
        'pdf',
        'xlsx',
        'xlsm',
        'xls',
        'csv',
        'tsv',
        'txt',
        'json',
        'png',
        'jpg',
        'jpeg',
        'webp',
        'bmp',
      ],
      withData: true,
    );
    if (pick == null || pick.files.isEmpty) return;
    final f = pick.files.first;
    final bytes = f.bytes;
    if (bytes == null || bytes.isEmpty) {
      setState(() => err = 'Could not read file bytes. Try another format or re-export.');
      return;
    }
    await _upload(f.name, bytes);
  }

  Future<void> _upload(String name, Uint8List bytes) async {
    setState(() {
      busy = true;
      err = null;
      fileLabel = name;
      result = null;
    });
    try {
      final r = await widget.state.uploadDocument(filename: name, bytes: bytes);
      setState(() => result = r);
      if (mounted) {
        final n = r['count'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Parsed $n holdings from $name')),
        );
      }
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _analyse() async {
    final holdings = (result?['holdings'] as List?)?.cast<dynamic>() ?? [];
    if (holdings.isEmpty) {
      setState(() => err = 'No holdings parsed — try PDF CAS, CSV export, or a clearer screenshot');
      return;
    }
    setState(() {
      busy = true;
      err = null;
    });
    try {
      await widget.state.analyseHoldings(
        holdings: holdings.map((h) => Map<String, dynamic>.from(h as Map)).toList(),
        questionnaire: {
          'goal': 'Wealth Creation',
          'target_amount': 5000000,
          'years': 10,
          'monthly_sip': 10000,
          'risk': 'moderate',
          'risk_response': 'moderate',
        },
      );
      widget.onAnalysed?.call();
    } catch (e) {
      setState(() => err = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final count = result?['count'] ?? 0;
    final kind = result?['kind']?.toString() ?? '—';
    final holdings = (result?['holdings'] as List?) ?? [];
    final formats = (result?['supported_formats'] as List?)?.join(' ') ??
        '.pdf .xlsx .csv .png .jpg .json .txt';

    return NxScaffold(
      title: 'Upload',
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('CAS · statements · screenshots', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                const SizedBox(height: 8),
                Text(
                  'Drop a portfolio document. Free local parse: PDF (CAS), Excel, CSV, JSON, or image OCR (Tesseract).',
                  style: const TextStyle(color: NxNavy.textSecondary, height: 1.4, fontSize: 13),
                ),
                const SizedBox(height: 10),
                Text('Formats: $formats', style: const TextStyle(color: NxNavy.textMuted, fontSize: 11, height: 1.35)),
              ],
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: busy ? null : _pick,
            icon: const Icon(Icons.upload_file_rounded),
            label: Text(busy ? 'Parsing…' : 'Choose file'),
          ),
          if (fileLabel != null) ...[
            const SizedBox(height: 10),
            Text('Selected: $fileLabel', style: const TextStyle(color: NxNavy.textSecondary, fontSize: 13)),
          ],
          if (err != null) ...[
            const SizedBox(height: 12),
            Text(err!, style: const TextStyle(color: NxNavy.danger, fontSize: 13)),
          ],
          if (result != null) ...[
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(child: KpiTile(label: 'Kind', value: kind)),
                const SizedBox(width: 10),
                Expanded(child: KpiTile(label: 'Holdings', value: '$count')),
              ],
            ),
            const SizedBox(height: 12),
            ...holdings.take(8).map((h) {
              final m = Map<String, dynamic>.from(h as Map);
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: NxNavy.surfaceElevated,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: NxNavy.border),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${m['name'] ?? ''}',
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                      ),
                    ),
                    Text(
                      '₹${m['current_value'] ?? 0}',
                      style: const TextStyle(color: NxNavy.accent, fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
              );
            }),
            if (holdings.length > 8)
              Text('+ ${holdings.length - 8} more', style: const TextStyle(color: NxNavy.textMuted, fontSize: 12)),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: busy || count == 0 ? null : _analyse,
              child: const Text('Run Health Check on these'),
            ),
          ],
          const SizedBox(height: 20),
          const Text(
            'Tips: MF Central / CAMS CAS PDF · Groww CSV · Coin XLSX · app screenshot PNG. Legacy .xls → save as .xlsx.',
            style: TextStyle(color: NxNavy.textMuted, fontSize: 11, height: 1.4),
          ),
        ],
      ),
    );
  }
}
