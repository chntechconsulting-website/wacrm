import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/mobile_sim_dialer.dart';
import '../../../core/utils/phone_utils.dart';

/// Standalone keypad for dialling any number from the device SIM.
///
/// Numbers entered here are not linked to a lead. They are still logged to the
/// CRM call log after the call ends, exactly like lead-based SIM calls.
class DialerScreen extends StatefulWidget {
  const DialerScreen({super.key});

  @override
  State<DialerScreen> createState() => _DialerScreenState();
}

class _DialerScreenState extends State<DialerScreen> {
  static const int _maxLength = 22;

  String _number = '';
  bool _isCalling = false;

  void _append(String value) {
    if (_isCalling) return;
    if ((_number + value).length > _maxLength) return;
    setState(() => _number += value);
  }

  void _backspace() {
    if (_isCalling || _number.isEmpty) return;
    setState(() => _number = _number.substring(0, _number.length - 1));
  }

  void _clear() {
    if (_isCalling || _number.isEmpty) return;
    setState(() => _number = '');
  }

  Future<void> _paste() async {
    if (_isCalling) return;
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final pasted = PhoneUtils.normalizeDialInput(data?.text);
    if (!mounted) return;
    if (pasted.replaceAll('+', '').length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Clipboard does not contain a valid number.'),
        ),
      );
      return;
    }
    setState(() => _number = pasted);
  }

  Future<void> _call() async {
    if (_isCalling) return;
    if (_number.replaceAll('+', '').length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter a phone number to call.')),
      );
      return;
    }

    FocusScope.of(context).unfocus();
    setState(() => _isCalling = true);
    final started = await MobileSimDialer.start(context, phone: _number);
    if (!mounted) return;
    setState(() => _isCalling = false);
    if (started) {
      setState(() => _number = '');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Dial Pad'),
        actions: [
          IconButton(
            tooltip: 'Paste number',
            icon: const Icon(Icons.content_paste_rounded),
            onPressed: _paste,
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final keySize =
                ((constraints.maxWidth - 96) / 3).clamp(64.0, 88.0).toDouble();
            return SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
              child: Column(
                children: [
                  _buildSimBanner(),
                  const SizedBox(height: 14),
                  _buildDisplay(),
                  const SizedBox(height: 12),
                  _buildKeypad(keySize),
                  const SizedBox(height: 18),
                  _buildCallButton(),
                  const SizedBox(height: 10),
                  const Text(
                    'Uses your mobile SIM, never the CRM PBX.\n'
                    'The call is logged to CRM after it ends.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 11,
                      height: 1.4,
                      color: AppColors.textLight,
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildSimBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFECFDF5),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFD1FAE5)),
      ),
      child: const Row(
        children: [
          Icon(Icons.sim_card_rounded, size: 18, color: Color(0xFF059669)),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Mobile SIM calling • customer sees your real caller ID',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                color: Color(0xFF047857),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDisplay() {
    final hasNumber = _number.isNotEmpty;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.border),
        boxShadow: AppColors.softShadow,
      ),
      child: Row(
        children: [
          Expanded(
            child: GestureDetector(
              onLongPress: _clear,
              child: Text(
                hasNumber ? _number : 'Enter a number',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: hasNumber ? 30 : 18,
                  fontWeight: hasNumber ? FontWeight.w700 : FontWeight.w500,
                  letterSpacing: hasNumber ? 0.8 : 0,
                  color: hasNumber ? AppColors.textMain : AppColors.textLight,
                ),
              ),
            ),
          ),
          if (hasNumber)
            IconButton(
              tooltip: 'Clear',
              icon: const Icon(Icons.close_rounded, size: 20),
              color: AppColors.textMuted,
              onPressed: _clear,
            ),
          IconButton(
            tooltip: 'Delete last digit',
            icon: const Icon(Icons.backspace_outlined, size: 21),
            color: AppColors.textMuted,
            onPressed: hasNumber ? _backspace : null,
          ),
        ],
      ),
    );
  }

  Widget _buildKeypad(double keySize) {
    const keys = <List<String>>[
      ['1', '2', '3'],
      ['4', '5', '6'],
      ['7', '8', '9'],
      ['*', '0', '#'],
    ];
    const letters = <String, String>{
      '2': 'ABC',
      '3': 'DEF',
      '4': 'GHI',
      '5': 'JKL',
      '6': 'MNO',
      '7': 'PQRS',
      '8': 'TUV',
      '9': 'WXYZ',
      '0': '+',
    };

    return Column(
      children: keys.map((row) {
        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: row.map((key) {
            final isZero = key == '0';
            return _DialKey(
              digit: key,
              letters: letters[key],
              size: keySize,
              onTap: () => _append(key),
              onLongPress: isZero ? () => _append('+') : null,
            );
          }).toList(),
        );
      }).toList(),
    );
  }

  Widget _buildCallButton() {
    return SizedBox(
      width: 156,
      height: 52,
      child: ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF10B981),
          foregroundColor: Colors.white,
          elevation: _isCalling ? 0 : 4,
          shadowColor: const Color(0xFF10B981).withValues(alpha: 0.4),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(26),
          ),
        ),
        icon: _isCalling
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.call_rounded, size: 21),
        label: Text(
          _isCalling ? 'Starting...' : 'Call',
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
        ),
        onPressed: _isCalling ? null : _call,
      ),
    );
  }
}

class _DialKey extends StatelessWidget {
  final String digit;
  final String? letters;
  final double size;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const _DialKey({
    required this.digit,
    required this.size,
    required this.onTap,
    this.letters,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Material(
        color: Colors.white,
        shape: const CircleBorder(),
        elevation: 0.5,
        shadowColor: const Color(0x220F172A),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          onLongPress: onLongPress,
          child: SizedBox(
            width: size,
            height: size,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  digit,
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w600,
                    height: 1.1,
                    color: AppColors.textMain,
                  ),
                ),
                if (letters != null && letters!.isNotEmpty)
                  Text(
                    letters!,
                    style: const TextStyle(
                      fontSize: 9,
                      letterSpacing: 0.8,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textLight,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
