import 'package:flutter/material.dart';

/// Nxance Navy design tokens — keep in sync with product/shared/navy_palette.json
class NxNavy {
  static const Color navy950 = Color(0xFF050B14);
  static const Color navy900 = Color(0xFF0A1628);
  static const Color navy800 = Color(0xFF0F2744);
  static const Color navy700 = Color(0xFF163A5F);
  static const Color navy600 = Color(0xFF1E4D7B);
  static const Color surface = Color(0xFF0C1A2E);
  static const Color surfaceElevated = Color(0xFF132741);
  static const Color card = Color(0xFF152C48);
  static const Color textPrimary = Color(0xFFF4F8FC);
  static const Color textSecondary = Color(0xFF9BB4CC);
  static const Color textMuted = Color(0xFF6B849C);
  static const Color accent = Color(0xFF3DDCFF);
  static const Color success = Color(0xFF3DDC97);
  static const Color warning = Color(0xFFF5B942);
  static const Color danger = Color(0xFFFF6B7A);
  static const Color border = Color(0x2E7AADD9);

  static ThemeData theme() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: 'Roboto',
    );
    return base.copyWith(
      scaffoldBackgroundColor: navy900,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        secondary: navy600,
        surface: surface,
        error: danger,
        onPrimary: navy950,
        onSurface: textPrimary,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: navy950,
        foregroundColor: textPrimary,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: border),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: navy950,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceElevated,
        hintStyle: const TextStyle(color: textMuted),
        labelStyle: const TextStyle(color: textSecondary),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: accent, width: 1.4),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: navy950,
        selectedItemColor: accent,
        unselectedItemColor: textMuted,
        type: BottomNavigationBarType.fixed,
      ),
      textTheme: base.textTheme.apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ),
    );
  }
}
