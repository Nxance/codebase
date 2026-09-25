import 'package:flutter/material.dart';
import '../state/app_state.dart';
import '../theme/navy.dart';
import '../widgets/widgets.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.state});
  final AppState state;
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final input = TextEditingController();
  final messages = <_Msg>[
    _Msg(bot: true, text: 'I explain engine numbers only. Run Health Check or Construction first.'),
  ];
  bool sending = false;

  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? input.text).trim();
    if (text.isEmpty) return;
    setState(() {
      messages.add(_Msg(bot: false, text: text));
      sending = true;
      input.clear();
    });
    try {
      final r = await widget.state.api.chat(text, reportId: widget.state.lastReportId);
      final reply = r['text']?.toString() ?? 'No reply';
      final guarded = r['number_guard_ok'] == false;
      setState(() {
        messages.add(_Msg(bot: true, text: guarded ? '$reply\n(number-guarded)' : reply));
      });
    } catch (e) {
      setState(() => messages.add(_Msg(bot: true, text: e.toString())));
    } finally {
      setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return NxScaffold(
      title: 'NxanceLM',
      child: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              itemCount: messages.length,
              itemBuilder: (_, i) {
                final m = messages[i];
                return Align(
                  alignment: m.bot ? Alignment.centerLeft : Alignment.centerRight,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
                    decoration: BoxDecoration(
                      color: m.bot ? NxNavy.card : NxNavy.navy700,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: NxNavy.border),
                    ),
                    child: Text(m.text, style: const TextStyle(height: 1.35, fontSize: 14)),
                  ),
                );
              },
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(children: [
              for (final q in ['What is my score?', 'Explain TER', 'What is XIRR?', 'Why these picks?'])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    label: Text(q, style: const TextStyle(fontSize: 12)),
                    backgroundColor: NxNavy.surfaceElevated,
                    onPressed: sending ? null : () => _send(q),
                  ),
                ),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: input,
                    decoration: const InputDecoration(hintText: 'Ask about your report…'),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: sending ? null : () => _send(),
                  style: IconButton.styleFrom(backgroundColor: NxNavy.accent, foregroundColor: NxNavy.navy950),
                  icon: const Icon(Icons.send_rounded),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Msg {
  _Msg({required this.bot, required this.text});
  final bool bot;
  final String text;
}
