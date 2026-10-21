import 'user_model.dart';

class AuthTokenModel {
  final String accessToken;
  final String tokenType;
  final UserModel user;

  AuthTokenModel({
    required this.accessToken,
    required this.tokenType,
    required this.user,
  });

  factory AuthTokenModel.fromJson(Map<String, dynamic> json) {
    return AuthTokenModel(
      accessToken: json['access_token'] ?? '',
      tokenType: json['token_type'] ?? 'bearer',
      user: UserModel.fromJson(json['user'] ?? {}),
    );
  }
}
