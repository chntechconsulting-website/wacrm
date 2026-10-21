import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/token_storage.dart';
import '../models/auth_token_model.dart';
import '../models/user_model.dart';

class AuthRepository {
  final ApiClient _client = ApiClient();

  Future<AuthTokenModel> login(String username, String password) async {
    final response = await _client.post(
      ApiEndpoints.login,
      body: {
        'username': username.trim(),
        'password': password,
      },
    );

    final tokenModel = AuthTokenModel.fromJson(response);
    await TokenStorage.saveToken(tokenModel.accessToken);
    await TokenStorage.saveUserData(tokenModel.user.toJson());
    return tokenModel;
  }

  Future<UserModel> getMe() async {
    final response = await _client.get(ApiEndpoints.me);
    final user = UserModel.fromJson(response);
    await TokenStorage.saveUserData(user.toJson());
    return user;
  }

  Future<void> logout() async {
    try {
      await _client.post(ApiEndpoints.logout);
    } catch (_) {
      // Ignore network errors on logout to ensure local session is cleared
    } finally {
      await TokenStorage.clearSession();
    }
  }
}
