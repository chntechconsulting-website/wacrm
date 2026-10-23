import 'package:flutter/material.dart';
import '../data/calls_repository.dart';
import '../models/call_log_model.dart';

class CallsProvider extends ChangeNotifier {
  final CallsRepository _repository = CallsRepository();

  List<CallLogModel> _calls = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<CallLogModel> get calls => _calls;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchCalls({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _calls = await _repository.getCalls();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> checkAgentExtension() async {
    return await _repository.getAgentExtension();
  }

  Future<bool> initiateDooctiCall({required String phone, int? leadId, String? notes}) async {
    try {
      await _repository.initiateDooctiCall(phone: phone, leadId: leadId, notes: notes);
      await fetchCalls(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> initiateCall({required String phone, int? leadId}) async {
    try {
      await _repository.initiateIvrCall(phone: phone, leadId: leadId);
      await fetchCalls(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> logManualCall({
    required String customerNumber,
    required String callStatus,
    required int durationSeconds,
    int? leadId,
    String? notes,
  }) async {
    try {
      await _repository.logManualCall(
        customerNumber: customerNumber,
        callStatus: callStatus,
        durationSeconds: durationSeconds,
        leadId: leadId,
        notes: notes,
      );
      await fetchCalls(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
