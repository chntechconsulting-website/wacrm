import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'api_exceptions.dart';
import 'token_storage.dart';

typedef OnUnauthorizedCallback = void Function();

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  final http.Client _httpClient = http.Client();
  final Duration _timeout = const Duration(seconds: 25);
  OnUnauthorizedCallback? onUnauthorized;

  Future<Map<String, String>> _getHeaders({bool isMultipart = false}) async {
    final headers = <String, String>{'Accept': 'application/json'};
    if (!isMultipart) {
      headers['Content-Type'] = 'application/json';
    }

    final token = await TokenStorage.getToken();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }

    return headers;
  }

  dynamic _processResponse(
    http.Response response, {
    bool isLoginEndpoint = false,
    String? url,
  }) {
    final statusCode = response.statusCode;
    final requestUrl = url ?? response.request?.url.toString() ?? '';
    final isExcludedFromLogout =
        isLoginEndpoint ||
        requestUrl.contains('/auth/login') ||
        requestUrl.contains('/auth/token') ||
        requestUrl.contains('/doocti/') ||
        requestUrl.contains('/ivr/') ||
        requestUrl.contains('/integrations/');
    dynamic body;

    try {
      if (response.body.isNotEmpty) {
        body = jsonDecode(utf8.decode(response.bodyBytes));
      }
    } catch (_) {
      body = response.body;
    }

    if (statusCode >= 200 && statusCode < 300) {
      return body;
    }

    String errorMessage = 'Request failed with status $statusCode';
    if (body is Map<String, dynamic>) {
      if (body.containsKey('detail')) {
        final detail = body['detail'];
        if (detail is String) {
          errorMessage = detail;
        } else if (detail is List && detail.isNotEmpty) {
          // Pydantic validation errors
          final first = detail.first;
          if (first is Map && first.containsKey('msg')) {
            errorMessage = '${first['loc']?.join(' -> ')}: ${first['msg']}';
          } else {
            errorMessage = detail.toString();
          }
        }
      } else if (body.containsKey('message')) {
        errorMessage = body['message'].toString();
      }
    }

    if (statusCode == 401) {
      if (!isExcludedFromLogout) {
        onUnauthorized?.call();
      }
      throw UnauthorizedException(errorMessage);
    } else if (statusCode == 403) {
      throw ForbiddenException(errorMessage);
    } else if (statusCode == 404) {
      throw NotFoundException(errorMessage);
    } else if (statusCode == 422) {
      throw ValidationException(errorMessage, details: body);
    } else {
      throw ApiException(errorMessage, statusCode: statusCode, details: body);
    }
  }

  Future<dynamic> get(
    String url, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      Uri uri = Uri.parse(url);
      if (queryParameters != null && queryParameters.isNotEmpty) {
        final cleanParams = <String, String>{};
        queryParameters.forEach((key, value) {
          if (value != null) {
            cleanParams[key] = value.toString();
          }
        });
        uri = uri.replace(queryParameters: cleanParams);
      }

      final headers = await _getHeaders();
      final response = await _httpClient
          .get(uri, headers: headers)
          .timeout(_timeout);
      return _processResponse(response, url: url);
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }

  Future<dynamic> post(String url, {dynamic body}) async {
    try {
      final uri = Uri.parse(url);
      final headers = await _getHeaders();
      final isLogin =
          url.contains('/auth/login') || url.contains('/auth/token');

      final encodedBody = body != null ? jsonEncode(body) : null;
      final response = await _httpClient
          .post(uri, headers: headers, body: encodedBody)
          .timeout(_timeout);

      return _processResponse(response, isLoginEndpoint: isLogin, url: url);
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }

  /// Uploads a local file as multipart/form-data (used for authorised call
  /// recordings). The bearer token is sent in the header, not the URL.
  Future<dynamic> postMultipart(
    String url, {
    required File file,
    String field = 'file',
    Map<String, String>? fields,
  }) async {
    try {
      final uri = Uri.parse(url);
      final headers = await _getHeaders(isMultipart: true);
      final request = http.MultipartRequest('POST', uri);
      request.headers.addAll(headers);
      if (fields != null && fields.isNotEmpty) {
        request.fields.addAll(fields);
      }
      request.files.add(await http.MultipartFile.fromPath(field, file.path));

      final streamed = await _httpClient
          .send(request)
          .timeout(const Duration(seconds: 120));
      final response = await http.Response.fromStream(streamed);
      return _processResponse(response, url: url);
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }

  Future<dynamic> put(String url, {dynamic body}) async {
    try {
      final uri = Uri.parse(url);
      final headers = await _getHeaders();
      final encodedBody = body != null ? jsonEncode(body) : null;

      final response = await _httpClient
          .put(uri, headers: headers, body: encodedBody)
          .timeout(_timeout);

      return _processResponse(response, url: url);
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }

  Future<dynamic> delete(String url) async {
    try {
      final uri = Uri.parse(url);
      final headers = await _getHeaders();
      final response = await _httpClient
          .delete(uri, headers: headers)
          .timeout(_timeout);
      return _processResponse(response, url: url);
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }

  Future<Uint8List> downloadBytes(String url) async {
    try {
      final uri = Uri.parse(url);
      final headers = await _getHeaders();
      final response = await _httpClient
          .get(uri, headers: headers)
          .timeout(const Duration(seconds: 40));

      if (response.statusCode == 200) {
        return response.bodyBytes;
      } else {
        _processResponse(response, url: url);
        throw ApiException(
          'Failed to download document',
          statusCode: response.statusCode,
        );
      }
    } on SocketException {
      throw NetworkException();
    } on http.ClientException {
      throw NetworkException();
    } on TimeoutException {
      throw TimeoutException();
    }
  }
}
