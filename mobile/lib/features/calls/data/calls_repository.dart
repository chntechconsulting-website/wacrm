import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/call_log_model.dart';

class CallsRepository {
  final ApiClient _client = ApiClient();

  Future<List<CallLogModel>> getCalls({int page = 1, int pageSize = 20}) async {
    final response = await _client.get(
      ApiEndpoints.ivrCalls,
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        'per_page': pageSize,
      },
    );

    if (response is Map && response.containsKey('calls')) {
      final list = response['calls'] as List;
      return list.map((json) => CallLogModel.fromJson(json)).toList();
    } else if (response is Map && response.containsKey('items')) {
      final list = response['items'] as List;
      return list.map((json) => CallLogModel.fromJson(json)).toList();
    } else if (response is List) {
      return response.map((json) => CallLogModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> getAgentExtension() async {
    try {
      final response = await _client.get(ApiEndpoints.dooctiAgentExtension);
      if (response is Map<String, dynamic>) {
        return response;
      }
      return {'registered': false};
    } catch (_) {
      return {'registered': false};
    }
  }

  Future<Map<String, dynamic>> initiateDooctiCall({
    required String phone,
    int? leadId,
    String? notes,
  }) async {
    final body = {
      'phone_number': phone,
      'phone': phone,
      'customer_phone': phone,
      if (leadId != null) 'lead_id': leadId,
      if (notes != null) 'notes': notes,
    };
    final response = await _client.post(ApiEndpoints.dooctiCall, body: body);
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {'status': 'success', 'data': response};
  }

  Future<void> initiateIvrCall({required String phone, int? leadId, String? notes}) async {
    final body = {
      'phone': phone,
      'customer_phone': phone,
      'phone_number': phone,
      if (leadId != null) 'lead_id': leadId,
      if (notes != null) 'notes': notes,
    };
    await _client.post(ApiEndpoints.initiateCall, body: body);
  }

  Future<void> logManualCall({
    String? customerNumber,
    String? customerPhone,
    required String callStatus,
    required int durationSeconds,
    int? leadId,
    String? notes,
  }) async {
    final effectivePhone = customerPhone ?? customerNumber ?? '';
    final body = {
      'customer_phone': effectivePhone,
      'customer_number': effectivePhone,
      'call_status': callStatus,
      'duration_seconds': durationSeconds,
      if (leadId != null) 'lead_id': leadId,
      if (notes != null) 'notes': notes,
    };

    try {
      await _client.post(ApiEndpoints.manualCall, body: body);
    } on ApiException catch (e) {
      if (e.statusCode == 404 || e.statusCode == 405) {
        await _client.post(ApiEndpoints.manualCallLegacy, body: body);
      } else {
        rethrow;
      }
    }
  }
}
