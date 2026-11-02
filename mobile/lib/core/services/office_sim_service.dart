import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/api_endpoints.dart';
import '../network/api_client.dart';
import 'mobile_sim_call_service.dart';

/// The employee's registered Office SIM as stored by the backend.
@immutable
class OfficeSimMapping {
  final int? id;
  final int? employeeId;
  final int? subscriptionId;
  final int? simSlot;
  final String carrierName;
  final String displayName;
  final String? phoneNumber;
  final String? phoneAccountId;
  final String? phoneAccountComponent;
  final String simFingerprint;
  final String status;
  final String? verificationReason;

  const OfficeSimMapping({
    this.id,
    this.employeeId,
    this.subscriptionId,
    this.simSlot,
    this.carrierName = '',
    this.displayName = '',
    this.phoneNumber,
    this.phoneAccountId,
    this.phoneAccountComponent,
    this.simFingerprint = '',
    this.status = 'REQUIRES_VERIFICATION',
    this.verificationReason,
  });

  bool get isVerified => status == 'VERIFIED';

  String get label {
    if (displayName.trim().isNotEmpty) return displayName.trim();
    if (carrierName.trim().isNotEmpty) return carrierName.trim();
    return simSlot == null ? 'Office SIM' : 'SIM ${simSlot! + 1}';
  }

  factory OfficeSimMapping.fromJson(Map<String, dynamic> json) {
    return OfficeSimMapping(
      id: (json['id'] as num?)?.toInt(),
      employeeId: (json['employee_id'] as num?)?.toInt(),
      subscriptionId: (json['subscription_id'] as num?)?.toInt(),
      simSlot: (json['sim_slot'] as num?)?.toInt(),
      carrierName: (json['carrier_name'] ?? '').toString(),
      displayName: (json['display_name'] ?? '').toString(),
      phoneNumber: json['phone_number']?.toString(),
      phoneAccountId: json['phone_account_id']?.toString(),
      phoneAccountComponent: json['phone_account_component']?.toString(),
      simFingerprint: (json['sim_fingerprint'] ?? '').toString(),
      status: (json['status'] ?? 'REQUIRES_VERIFICATION').toString(),
      verificationReason: json['verification_reason']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'configured': true,
    'id': id,
    'employee_id': employeeId,
    'subscription_id': subscriptionId,
    'sim_slot': simSlot,
    'carrier_name': carrierName,
    'display_name': displayName,
    'phone_number': phoneNumber,
    'phone_account_id': phoneAccountId,
    'phone_account_component': phoneAccountComponent,
    'sim_fingerprint': simFingerprint,
    'status': status,
    'verification_reason': verificationReason,
  };

  OfficeSimMapping copyWith({String? status, String? verificationReason}) {
    return OfficeSimMapping(
      id: id,
      employeeId: employeeId,
      subscriptionId: subscriptionId,
      simSlot: simSlot,
      carrierName: carrierName,
      displayName: displayName,
      phoneNumber: phoneNumber,
      phoneAccountId: phoneAccountId,
      phoneAccountComponent: phoneAccountComponent,
      simFingerprint: simFingerprint,
      status: status ?? this.status,
      verificationReason: verificationReason ?? this.verificationReason,
    );
  }
}

enum OfficeSimState {
  notConfigured,
  verified,
  requiresVerification,
  unsupported,
}

class OfficeSimEvaluation {
  final OfficeSimState state;
  final OfficeSimMapping? mapping;
  final SimAccount? sim;
  final String message;

  const OfficeSimEvaluation({
    required this.state,
    this.mapping,
    this.sim,
    this.message = '',
  });

  bool get canSync => state == OfficeSimState.verified;
}

class OfficeSimService {
  static final ApiClient _client = ApiClient();
  static const String _cacheKey = 'wacrm_office_sim_mapping_v1';

  static OfficeSimMapping? _memory;

  static Future<OfficeSimMapping?> cached() async {
    if (_memory != null) return _memory;
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_cacheKey);
      if (raw == null || raw.isEmpty) return null;
      final map = jsonDecode(raw);
      if (map is! Map) return null;
      _memory = OfficeSimMapping.fromJson(Map<String, dynamic>.from(map));
      return _memory;
    } catch (_) {
      return null;
    }
  }

  static Future<void> _cache(OfficeSimMapping? mapping) async {
    _memory = mapping;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (mapping == null) {
        await prefs.remove(_cacheKey);
      } else {
        await prefs.setString(_cacheKey, jsonEncode(mapping.toJson()));
      }
    } catch (_) {
      // Local cache is best-effort.
    }
  }

  /// Reads the server mapping. Falls back to the last known copy offline.
  static Future<OfficeSimMapping?> fetch({bool force = false}) async {
    if (!force) {
      final local = await cached();
      if (local != null) {
        // Refresh in the background on the next explicit call, but never block
        // sync on a slow network when a verified local copy exists.
        unawaited(_refreshFromServer());
        return local;
      }
    }
    return _refreshFromServer();
  }

  static Future<OfficeSimMapping?> _refreshFromServer() async {
    try {
      final response = await _client.get(ApiEndpoints.officeSim);
      if (response is! Map) return await cached();
      final map = Map<String, dynamic>.from(response);
      if (map['configured'] != true) {
        await _cache(null);
        return null;
      }
      final mapping = OfficeSimMapping.fromJson(map);
      await _cache(mapping);
      return mapping;
    } catch (_) {
      return cached();
    }
  }

  static Future<OfficeSimMapping> save(SimAccount sim) async {
    final response = await _client.put(
      ApiEndpoints.officeSim,
      body: {
        'subscription_id': sim.subscriptionId >= 0 ? sim.subscriptionId : null,
        'sim_slot': sim.slotIndex,
        'carrier_name': sim.carrierName,
        'display_name': sim.displayName,
        'phone_number': sim.phoneNumber,
        'phone_account_id': sim.phoneAccountId,
        'phone_account_component': sim.phoneAccountComponent,
        'sim_fingerprint': (sim.simFingerprint ?? '').trim().isEmpty
            ? _fallbackFingerprint(sim)
            : sim.simFingerprint,
      },
    );
    final map = Map<String, dynamic>.from(response as Map);
    final mapping = OfficeSimMapping.fromJson(map);
    await _cache(mapping);
    return mapping;
  }

  static Future<OfficeSimMapping?> markRequiresVerification(String reason) async {
    try {
      final response = await _client.post(
        ApiEndpoints.officeSimStatus,
        body: {'status': 'REQUIRES_VERIFICATION', 'reason': reason},
      );
      if (response is Map) {
        final mapping = OfficeSimMapping.fromJson(
          Map<String, dynamic>.from(response),
        );
        await _cache(mapping);
        return mapping;
      }
    } catch (_) {
      // Keep a local fail-closed copy even when offline.
    }
    final local = await cached();
    if (local == null) return null;
    final updated = local.copyWith(
      status: 'REQUIRES_VERIFICATION',
      verificationReason: reason,
    );
    await _cache(updated);
    return updated;
  }

  static Future<void> clear() async {
    try {
      await _client.delete(ApiEndpoints.officeSim);
    } catch (_) {
      // Local removal still stops synchronization on this device.
    }
    await _cache(null);
  }

  /// Drops the device cache only. Used on logout so the next employee on this
  /// device can never inherit another employee's Office SIM mapping.
  static Future<void> clearLocalCache() async {
    await _cache(null);
  }

  /// Compares the stored mapping with the SIMs currently installed.
  ///
  /// Any missing SIM, changed subscription/phone-account identity or changed
  /// fingerprint pauses synchronization and requires explicit re-verification.
  static Future<OfficeSimEvaluation> evaluate({bool reportChange = true}) async {
    if (kIsWeb || !Platform.isAndroid) {
      return const OfficeSimEvaluation(
        state: OfficeSimState.unsupported,
        message: 'Office SIM configuration is available on Android only.',
      );
    }
    final mapping = await fetch();
    if (mapping == null) {
      return const OfficeSimEvaluation(
        state: OfficeSimState.notConfigured,
        message: 'Select your Office SIM to enable CRM call synchronization.',
      );
    }
    if (!mapping.isVerified) {
      return OfficeSimEvaluation(
        state: OfficeSimState.requiresVerification,
        mapping: mapping,
        message: mapping.verificationReason?.trim().isNotEmpty == true
            ? mapping.verificationReason!
            : 'The Office SIM must be re-verified on this device.',
      );
    }

    final sims = await MobileSimCallService.getSimAccounts();
    final current = matchSim(mapping, sims);
    if (current == null) {
      const reason =
          'The registered Office SIM is not present on this device. '
          'Synchronization is paused until it is re-verified.';
      final updated = reportChange
          ? await markRequiresVerification(reason)
          : mapping.copyWith(
              status: 'REQUIRES_VERIFICATION',
              verificationReason: reason,
            );
      return OfficeSimEvaluation(
        state: OfficeSimState.requiresVerification,
        mapping: updated,
        message: reason,
      );
    }

    final storedFingerprint = mapping.simFingerprint.trim();
    final currentFingerprint = (current.simFingerprint ?? '').trim();
    if (storedFingerprint.isNotEmpty &&
        currentFingerprint.isNotEmpty &&
        storedFingerprint != currentFingerprint) {
      const reason =
          'The Office SIM identity changed on this device. '
          'Synchronization is paused until it is re-verified.';
      final updated = reportChange
          ? await markRequiresVerification(reason)
          : mapping.copyWith(
              status: 'REQUIRES_VERIFICATION',
              verificationReason: reason,
            );
      return OfficeSimEvaluation(
        state: OfficeSimState.requiresVerification,
        mapping: updated,
        sim: current,
        message: reason,
      );
    }

    return OfficeSimEvaluation(
      state: OfficeSimState.verified,
      mapping: mapping,
      sim: current,
      message: 'Office SIM verified.',
    );
  }

  static SimAccount? matchSim(OfficeSimMapping mapping, List<SimAccount> sims) {
    if (mapping.subscriptionId != null) {
      for (final sim in sims) {
        if (sim.subscriptionId == mapping.subscriptionId) return sim;
      }
      return null;
    }
    final account = (mapping.phoneAccountId ?? '').trim();
    if (account.isEmpty) return null;
    final component = (mapping.phoneAccountComponent ?? '').trim();
    for (final sim in sims) {
      if ((sim.phoneAccountId ?? '').trim() != account) continue;
      if (component.isNotEmpty &&
          (sim.phoneAccountComponent ?? '').trim() != component) {
        continue;
      }
      return sim;
    }
    return null;
  }

  /// Exact identity match for a call row. Never falls back to slot or number.
  static bool callMatches(
    OfficeSimMapping mapping, {
    int? subscriptionId,
    String? simAccountId,
  }) {
    if (subscriptionId != null && mapping.subscriptionId == subscriptionId) {
      return true;
    }
    final token = (simAccountId ?? '').trim();
    if (token.isEmpty) return false;
    if (mapping.subscriptionId != null && token == 'subId:${mapping.subscriptionId}') {
      return true;
    }
    final account = (mapping.phoneAccountId ?? '').trim();
    if (account.isEmpty) return false;
    final component = (mapping.phoneAccountComponent ?? '').trim();
    if (token == account || token == 'phoneAccount:$account') return true;
    if (component.isNotEmpty) {
      return token == 'phoneAccount:$component#$account' ||
          token == 'phoneAccount:$component|$account';
    }
    return false;
  }

  /// true when the call may be synchronized. When no mapping exists, legacy
  /// behaviour is preserved; once configured, only exact Office SIM calls pass.
  static Future<bool> allowsCall({
    int? subscriptionId,
    String? simAccountId,
  }) async {
    final mapping = await fetch();
    if (mapping == null) return true;
    if (!mapping.isVerified) return false;
    return callMatches(
      mapping,
      subscriptionId: subscriptionId,
      simAccountId: simAccountId,
    );
  }

  static String _fallbackFingerprint(SimAccount sim) {
    return [
      sim.subscriptionId,
      sim.slotIndex,
      sim.carrierName,
      sim.displayName,
      sim.phoneNumber ?? '',
      sim.phoneAccountId ?? '',
      sim.phoneAccountComponent ?? '',
    ].join('|');
  }
}
