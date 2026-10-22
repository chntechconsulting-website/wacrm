import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/followup_model.dart';

class FollowupsRepository {
  final ApiClient _client = ApiClient();

  Future<List<FollowupModel>> getFollowups({
    String? status,
    String? priority,
    String? dateFilter,
    String? search,
  }) async {
    final params = <String, dynamic>{};
    if (status != null && status.isNotEmpty && status != 'ALL') {
      params['status_filter'] = status;
      params['status'] = status;
    }
    if (priority != null && priority.isNotEmpty && priority != 'ALL') {
      params['priority_filter'] = priority;
      params['priority'] = priority;
    }
    if (dateFilter != null && dateFilter.isNotEmpty && dateFilter != 'ALL') {
      params['date_filter'] = dateFilter;
    }
    if (search != null && search.isNotEmpty) {
      params['search'] = search;
    }

    final response = await _client.get(ApiEndpoints.followups, queryParameters: params);
    if (response is List) {
      return response.map((json) => FollowupModel.fromJson(json)).toList();
    } else if (response is Map) {
      if (response['items'] is List) {
        return (response['items'] as List).map((json) => FollowupModel.fromJson(json)).toList();
      } else if (response['followups'] is List) {
        return (response['followups'] as List).map((json) => FollowupModel.fromJson(json)).toList();
      } else if (response['data'] is List) {
        return (response['data'] as List).map((json) => FollowupModel.fromJson(json)).toList();
      }
    }
    return [];
  }

  Future<List<FollowupReminderModel>> getActiveReminders() async {
    final response = await _client.get(ApiEndpoints.activeReminders);
    if (response is List) {
      return response.map((json) => FollowupReminderModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<FollowupModel> createFollowup(Map<String, dynamic> data) async {
    final response = await _client.post(ApiEndpoints.followups, body: data);
    return FollowupModel.fromJson(response);
  }

  Future<FollowupModel> updateFollowup(int id, Map<String, dynamic> data) async {
    final response = await _client.put(ApiEndpoints.followupById(id), body: data);
    return FollowupModel.fromJson(response);
  }

  Future<void> deleteFollowup(int id) async {
    await _client.delete(ApiEndpoints.followupById(id));
  }

  Future<void> snoozeReminder(int id, {int minutes = 30}) async {
    await _client.post(ApiEndpoints.snoozeReminder(id), body: {'minutes': minutes});
  }

  Future<void> dismissReminder(int id) async {
    await _client.post(ApiEndpoints.dismissReminder(id));
  }
}
