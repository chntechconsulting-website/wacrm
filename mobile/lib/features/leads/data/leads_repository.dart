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
    int? assignedTo,
    bool? isReinquiry,
    String? dateFilter,
    String? startDate,
    String? endDate,
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
    if (status != null && status.isNotEmpty && status != 'ALL') {
      params['status_filter'] = status;
      params['status'] = status;
    }
    if (source != null && source.isNotEmpty && source != 'ALL') {
      params['source_filter'] = source;
      params['source'] = source;
    }
    if (priority != null && priority.isNotEmpty && priority != 'ALL') {
      params['priority_filter'] = priority;
      params['priority'] = priority;
    }
    if (assignedTo != null) {
      params['assigned_to_filter'] = assignedTo;
      params['assigned_to'] = assignedTo;
    }
    if (isReinquiry != null) {
      params['is_reinquiry_filter'] = isReinquiry;
    }
    if (dateFilter != null && dateFilter.isNotEmpty && dateFilter != 'ALL') {
      params['date_filter'] = dateFilter;
    }
    if (startDate != null && startDate.isNotEmpty) {
      params['start_date'] = startDate;
    }
    if (endDate != null && endDate.isNotEmpty) {
      params['end_date'] = endDate;
    }

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

  Future<Map<String, int>> getLeadStats({bool onlyMy = false}) async {
    try {
      final response = await _client.get(
        ApiEndpoints.leadStats,
        queryParameters: onlyMy ? {'only_my': true} : null,
      );
      if (response is Map) {
        return {
          'allLeads': (response['allLeads'] as num?)?.toInt() ?? 0,
          'metaLeads': (response['metaLeads'] as num?)?.toInt() ?? 0,
          'websiteLeads': (response['websiteLeads'] as num?)?.toInt() ?? 0,
          'manualLeads': (response['manualLeads'] as num?)?.toInt() ?? 0,
          'excelLeads': (response['excelLeads'] as num?)?.toInt() ?? 0,
          'reinquiryLeads': (response['reinquiryLeads'] as num?)?.toInt() ?? 0,
          'newLeads': (response['newLeads'] as num?)?.toInt() ?? 0,
          'inProgressLeads': (response['inProgressLeads'] as num?)?.toInt() ?? 0,
          'hotLeads': (response['hotLeads'] as num?)?.toInt() ?? 0,
          'wonLeads': (response['wonLeads'] as num?)?.toInt() ?? 0,
          'myLeads': (response['myLeads'] as num?)?.toInt() ?? 0,
        };
      }
    } catch (_) {}
    return {};
  }

  Future<List<SupportManagerOption>> getSupportManagers() async {
    final response = await _client.get(ApiEndpoints.supportManagers);
    if (response is List) {
      return response.map((json) => SupportManagerOption.fromJson(json)).toList();
    }
    return [];
  }

  Future<List<ProformaOption>> getLeadProformas(int leadId) async {
    final response = await _client.get(ApiEndpoints.leadProformas(leadId));
    if (response is List) {
      return response.map((json) => ProformaOption.fromJson(json)).toList();
    }
    return [];
  }

  Future<dynamic> markLeadWon(int leadId, Map<String, dynamic> payload) async {
    final response = await _client.post(
      ApiEndpoints.leadWon(leadId),
      body: payload,
    );
    return response;
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
