import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/activity_model.dart';

class ActivitiesRepository {
  final ApiClient _client = ApiClient();

  Future<List<ActivityModel>> getActivities({int? leadId, int? employeeId, int limit = 50}) async {
    final params = <String, dynamic>{'limit': limit};
    if (leadId != null) params['lead_id'] = leadId;
    if (employeeId != null) params['employee_id'] = employeeId;

    final response = await _client.get(ApiEndpoints.activities, queryParameters: params);
    if (response is List) {
      return response.map((json) => ActivityModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<ActivityModel> createActivity(Map<String, dynamic> data) async {
    final response = await _client.post(ApiEndpoints.activities, body: data);
    return ActivityModel.fromJson(response);
  }
}
