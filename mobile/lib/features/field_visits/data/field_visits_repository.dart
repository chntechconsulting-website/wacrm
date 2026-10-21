import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/field_visit_model.dart';

class FieldVisitsRepository {
  final ApiClient _client = ApiClient();

  Future<List<FieldVisitModel>> getFieldVisits({
    int? employeeId,
    int? leadId,
    int? customerId,
    String? status,
    int limit = 100,
  }) async {
    final params = <String, dynamic>{'limit': limit};
    if (employeeId != null) params['employee_id'] = employeeId;
    if (leadId != null) params['lead_id'] = leadId;
    if (customerId != null) params['customer_id'] = customerId;
    if (status != null && status.isNotEmpty) params['status'] = status;

    final response = await _client.get(ApiEndpoints.fieldVisits, queryParameters: params);
    if (response is List) {
      return response.map((json) => FieldVisitModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<FieldVisitModel> getFieldVisitById(int id) async {
    final response = await _client.get(ApiEndpoints.fieldVisitById(id));
    return FieldVisitModel.fromJson(response);
  }

  Future<FieldVisitModel> submitFieldVisit(Map<String, dynamic> data) async {
    final response = await _client.post(ApiEndpoints.fieldVisits, body: data);
    return FieldVisitModel.fromJson(response);
  }
}
