import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// One device call-log row that has not yet been confirmed by the CRM.
///
/// Entries are stored under one SharedPreferences key per native call
/// reference. That keeps concurrent Flutter isolates (the UI and the headless
/// background engine) from overwriting each other's read-modify-write state,
/// and makes the Android CallLog id the single queue identity.
class PendingCallSyncEntry {
  final String nativeReference;
  final Map<String, dynamic> row;
  final DateTime queuedAt;
  final int attempts;
  final String? lastError;
  final DateTime? lastAttemptAt;

  /// False when the last failure was permanent (for example HTTP 422). Such an
  /// entry is kept so no call is silently discarded, but automatic background
  /// passes skip it until the employee runs a manual sync.
  final bool retryable;

  const PendingCallSyncEntry({
    required this.nativeReference,
    required this.row,
    required this.queuedAt,
    this.attempts = 0,
    this.lastError,
    this.lastAttemptAt,
    this.retryable = true,
  });

  int? get dateMillis => _int(row['dateMillis']);
  int? get callLogId => _int(row['deviceCallLogId']);

  factory PendingCallSyncEntry.fromJson(Map<String, dynamic> json) {
    final rawRow = json['row'];
    final row = rawRow is Map
        ? Map<String, dynamic>.from(rawRow)
        : <String, dynamic>{};
    return PendingCallSyncEntry(
      nativeReference: (json['nativeReference'] ?? '').toString().trim(),
      row: row,
      queuedAt:
          DateTime.tryParse((json['queuedAt'] ?? '').toString())?.toUtc() ??
          DateTime.now().toUtc(),
      attempts: _int(json['attempts']) ?? 0,
      lastError: (json['lastError'] ?? '').toString().trim().isEmpty
          ? null
          : json['lastError'].toString(),
      lastAttemptAt: DateTime.tryParse((json['lastAttemptAt'] ?? '').toString())
          ?.toUtc(),
      retryable: json['retryable'] != false,
    );
  }

  Map<String, dynamic> toJson() => {
    'nativeReference': nativeReference,
    'row': row,
    'queuedAt': queuedAt.toIso8601String(),
    'attempts': attempts,
    'lastError': lastError,
    'lastAttemptAt': lastAttemptAt?.toIso8601String(),
    'retryable': retryable,
  };
}

/// Persistent, per-employee queue of call-log rows awaiting backend
/// confirmation.
class PendingCallSyncQueue {
  static const String _prefixBase = 'wacrm_pending_call_sync_v1';

  final String _scope;
  final List<PendingCallSyncEntry> _entries = <PendingCallSyncEntry>[];
  bool _loaded = false;

  PendingCallSyncQueue(String employeeKey)
    : _scope = employeeKey.trim().isEmpty ? 'default' : employeeKey.trim();

  String get _prefix => '${_prefixBase}_${_scope}_';

  List<PendingCallSyncEntry> get entries {
    final copy = List<PendingCallSyncEntry>.of(_entries);
    copy.sort(_byCallOrder);
    return List<PendingCallSyncEntry>.unmodifiable(copy);
  }

  int get count => _entries.length;

  int get retryableCount => _entries.where((entry) => entry.retryable).length;

  bool contains(String nativeReference) {
    final reference = nativeReference.trim();
    if (reference.isEmpty) return false;
    return _entries.any((entry) => entry.nativeReference == reference);
  }

  Future<void> reload() async {
    _entries.clear();
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final key in prefs.getKeys()) {
        if (!key.startsWith(_prefix)) continue;
        final raw = prefs.getString(key);
        if (raw == null || raw.isEmpty) continue;
        try {
          final decoded = jsonDecode(raw);
          if (decoded is! Map) continue;
          final entry = PendingCallSyncEntry.fromJson(
            Map<String, dynamic>.from(decoded),
          );
          if (entry.nativeReference.isEmpty) continue;
          _entries.add(entry);
        } catch (_) {
          // Ignore a single corrupted entry; the native call log still holds
          // the source row for a later pass.
        }
      }
    } catch (_) {
      // A storage failure must not break call scanning.
    }
    _loaded = true;
  }

  Future<PendingCallSyncEntry?> enqueue(Map<String, dynamic> row) async {
    final reference = (row['nativeCallReference'] ?? '').toString().trim();
    if (reference.isEmpty) return null;
    if (!_loaded) await reload();
    for (final existing in _entries) {
      if (existing.nativeReference == reference) return existing;
    }
    final entry = PendingCallSyncEntry(
      nativeReference: reference,
      row: Map<String, dynamic>.from(row),
      queuedAt: DateTime.now().toUtc(),
    );
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('$_prefix$reference', jsonEncode(entry.toJson()));
      _entries.add(entry);
      return entry;
    } catch (_) {
      // Without local storage the row is still retried from the call log.
      return null;
    }
  }

  Future<void> markFailure(
    PendingCallSyncEntry entry,
    Object error, {
    required bool retryable,
  }) async {
    final updated = PendingCallSyncEntry(
      nativeReference: entry.nativeReference,
      row: entry.row,
      queuedAt: entry.queuedAt,
      attempts: entry.attempts + 1,
      lastError: error.toString(),
      lastAttemptAt: DateTime.now().toUtc(),
      retryable: retryable,
    );
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        '$_prefix${entry.nativeReference}',
        jsonEncode(updated.toJson()),
      );
    } catch (_) {
      // Keep the in-memory copy so the current pass can report the failure.
    }
    final index = _entries.indexWhere(
      (candidate) => candidate.nativeReference == entry.nativeReference,
    );
    if (index >= 0) {
      _entries[index] = updated;
    } else {
      _entries.add(updated);
    }
  }

  Future<void> remove(PendingCallSyncEntry entry) async {
    await removeByReference(entry.nativeReference);
  }

  Future<void> removeByReference(String nativeReference) async {
    final reference = nativeReference.trim();
    if (reference.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('$_prefix$reference');
    } catch (_) {
      // Best effort: a stale queue entry is deduped by its native reference.
    }
    _entries.removeWhere((entry) => entry.nativeReference == reference);
  }

  Future<void> clear() async {
    final references = _entries
        .map((entry) => entry.nativeReference)
        .toList(growable: false);
    _entries.clear();
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final reference in references) {
        await prefs.remove('$_prefix$reference');
      }
    } catch (_) {
      // Best effort.
    }
  }

  /// Number of calls waiting for backend confirmation for this employee.
  static Future<int> pendingCount(String employeeKey) async {
    final queue = PendingCallSyncQueue(employeeKey);
    await queue.reload();
    return queue.count;
  }

  static int _byCallOrder(PendingCallSyncEntry a, PendingCallSyncEntry b) {
    final aDate = a.dateMillis ?? 0;
    final bDate = b.dateMillis ?? 0;
    if (aDate != bDate) return aDate.compareTo(bDate);
    final aId = a.callLogId ?? 0;
    final bId = b.callLogId ?? 0;
    return aId.compareTo(bId);
  }
}

int? _int(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}
