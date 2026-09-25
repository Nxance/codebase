import 'package:flutter_test/flutter_test.dart';
import 'package:nxance_mobile/main.dart';

void main() {
  testWidgets('Nxance app builds login shell', (WidgetTester tester) async {
    await tester.pumpWidget(const NxanceApp());
    expect(find.text('Sign in'), findsOneWidget);
  });
}
