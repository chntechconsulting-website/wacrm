import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/lead_model.dart';

class LeadsRepository {
  final ApiClient _client = ApiClient();

  Future<List<LeadModel>> getLeads({
    int skip = 0,
    int limit = 20,
    int? page,
    int? perPage,
    String? search,
    String? status,
    String? source,
    String? priority,
  }) async {
    final effectivePage = page ?? ((limit > 0 ? (skip ~/ limit) : 0) + 1);
    final effectivePerPage = perPage ?? limit;

    final params = <String, dynamic>{
      'skip': skip,
      'limit': limit,
      'page': effectivePage,
      'per_page': effectivePerPage,
    };
    if (search != null && search.isNotEmpty) params['search'] = search;
    if (status != null && status.isNotEmpty && status != 'ALL') params['status'] = status;
    if (source != null && source.isNotEmpty && source != 'ALL') params['source'] = source;
    if (priority != null && priority.isNotEmpty && priority != 'ALL') params['priority'] = priority;

    final response = await _client.get(ApiEndpoints.leads, queryParameters: params);
    if (response is List) {
      return response.map((json) => LeadModel.fromJson(json)).toList();
    } else if (response is Map) {
      if (response['items'] is List) {
        return (response['items'] as List).map((json) => LeadModel.fromJson(json)).toList();
      } else if (response['leads'] is List) {
        return (response['leads'] as List).map((json) => LeadModel.fromJson(json)).toList();
      } else if (response['data'] is List) {
        return (response['data'] as List).map((json) => LeadModel.fromJson(json)).toList();
      }
    }
    return [];
  }

  Future<LeadModel> getLeadById(int id) async {
    final response = await _client.get(ApiEndpoints.leadById(id));
    return LeadModel.fromJson(response);
  }

  Future<LeadModel> createLead(Map<String, dynamic> data) async {
    final response = await _client.post(ApiEndpoints.leads, body: data);
    return LeadModel.fromJson(response);
  }

  Future<LeadModel> updateLead(int id, Map<String, dynamic> data) async {
    final response = await _client.put(ApiEndpoints.leadById(id), body: data);
    return LeadModel.fromJson(response);
  }

  Future<LeadModel> updateLeadStatus(int id, String status) async {
    final response = await _client.put(
      ApiEndpoints.leadStatus(id),
      body: {'status': status},
    );
    return LeadModel.fromJson(response);
  }

  Future<LeadModel> assignLead(int id, int employeeId, {String? notes}) async {
    final body = {
      'assigned_to': employeeId,
      if (notes != null) 'notes': notes,
    };
    try {
      final response = await _client.post(
        ApiEndpoints.leadAssign(id),
        body: body,
      );
      return LeadModel.fromJson(response);
    } on ApiException catch (e) {
      if (e.statusCode == 405) {
        final response = await _client.put(
          ApiEndpoints.leadAssign(id),
          body: body,
        );
        return LeadModel.fromJson(response);
      }
      rethrow;
    }
  }

  Future<void> addLeadNote(int id, String note) async {
    await _client.post(
      ApiEndpoints.leadNotes(id),
      body: {'note': note},
    );
  }

  Future<void> deleteLead(int id) async {
    await _client.delete(ApiEndpoints.leadById(id));
  }

  Future<List<EmployeeOption>> getEmployees() async {
    final response = await _client.get(ApiEndpoints.employees);
    if (response is List) {
      return response.map((json) => EmployeeOption.fromJson(json)).toList();
    }
    return [];
  }
}
