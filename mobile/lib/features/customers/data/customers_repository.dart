import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/customer_model.dart';

class CustomersRepository {
  final ApiClient _client = ApiClient();

  Future<List<CustomerModel>> getCustomers({
    String? search,
    int skip = 0,
    int limit = 20,
    int? page,
    int? perPage,
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

    final response = await _client.get(ApiEndpoints.customers, queryParameters: params);
    if (response is List) {
      return response.map((json) => CustomerModel.fromJson(json)).toList();
    } else if (response is Map) {
      if (response['items'] is List) {
        return (response['items'] as List).map((json) => CustomerModel.fromJson(json)).toList();
      } else if (response['customers'] is List) {
        return (response['customers'] as List).map((json) => CustomerModel.fromJson(json)).toList();
      } else if (response['data'] is List) {
        return (response['data'] as List).map((json) => CustomerModel.fromJson(json)).toList();
      }
    }
    return [];
  }

  Future<CustomerModel> getCustomerById(int id) async {
    final response = await _client.get(ApiEndpoints.customerById(id));
    return CustomerModel.fromJson(response);
  }
}
