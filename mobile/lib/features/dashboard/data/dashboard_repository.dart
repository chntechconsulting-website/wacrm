import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/dashboard_stats_model.dart';

class DashboardRepository {
  final ApiClient _client = ApiClient();

  Future<DashboardStatsModel> getDashboardStats() async {
    final response = await _client.get(ApiEndpoints.dashboardStats);
    return DashboardStatsModel.fromJson(response);
  }
}
