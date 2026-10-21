import 'package:flutter/material.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/token_storage.dart';
import '../data/auth_repository.dart';
import '../models/user_model.dart';

enum AuthStatus { uninitialized, authenticated, unauthenticated, loading }

class AuthProvider extends ChangeNotifier {
  final AuthRepository _repository = AuthRepository();
  UserModel? _currentUser;
  AuthStatus _status = AuthStatus.uninitialized;
  String? _errorMessage;

  UserModel? get currentUser => _currentUser;
  AuthStatus get status => _status;
  bool get isAuthenticated => _status == AuthStatus.authenticated && _currentUser != null;
  String? get errorMessage => _errorMessage;

  AuthProvider() {
    // Register global unauthorized (401) listener
    ApiClient().onUnauthorized = () {
      logout();
    };
  }

  Future<void> initAuth() async {
    _status = AuthStatus.loading;
    notifyListeners();

    final savedUrl = await TokenStorage.getServerUrl();
    if (savedUrl != null &&
        savedUrl.isNotEmpty &&
        !savedUrl.contains('10.0.2.2')) {
      var url = savedUrl.trim().replaceAll(RegExp(r'/+$'), '');
      if (url.endsWith('/api')) {
        url = url.substring(0, url.length - 4);
      }
      if (url.startsWith('http://www.wapluscrm.in')) {
        url = url.replaceFirst('http://', 'https://');
      }
      ApiEndpoints.baseUrl = url;
    } else {
      ApiEndpoints.baseUrl = ApiEndpoints.productionBaseUrl;
      await TokenStorage.saveServerUrl(ApiEndpoints.productionBaseUrl);
    }

    final token = await TokenStorage.getToken();
    final cachedUser = await TokenStorage.getUserData();

    if (token != null && token.isNotEmpty) {
      if (cachedUser != null) {
        _currentUser = UserModel.fromJson(cachedUser);
      }
      try {
        _currentUser = await _repository.getMe();
        _status = AuthStatus.authenticated;
      } catch (e) {
        // If token invalid, unauthenticate; if network error, keep cached user
        if (e.toString().contains('401') || e.toString().contains('expired')) {
          await TokenStorage.clearSession();
          _currentUser = null;
          _status = AuthStatus.unauthenticated;
        } else if (_currentUser != null) {
          _status = AuthStatus.authenticated;
        } else {
          _status = AuthStatus.unauthenticated;
        }
      }
    } else {
      _status = AuthStatus.unauthenticated;
    }

    notifyListeners();
  }

  Future<bool> login(String username, String password, {bool rememberMe = true}) async {
    _status = AuthStatus.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      final tokenModel = await _repository.login(username, password);
      _currentUser = tokenModel.user;
      _status = AuthStatus.authenticated;

      if (rememberMe) {
        await TokenStorage.saveRememberedUsername(username);
      }

      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      _status = AuthStatus.unauthenticated;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    _status = AuthStatus.loading;
    notifyListeners();

    await _repository.logout();
    _currentUser = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  void updateServerUrl(String newUrl) {
    var url = newUrl.trim().replaceAll(RegExp(r'/+$'), '');
    if (url.endsWith('/api')) {
      url = url.substring(0, url.length - 4);
    }
    if (url.startsWith('http://www.wapluscrm.in')) {
      url = url.replaceFirst('http://', 'https://');
    }
    ApiEndpoints.baseUrl = url;
    TokenStorage.saveServerUrl(url);
    notifyListeners();
  }
}
