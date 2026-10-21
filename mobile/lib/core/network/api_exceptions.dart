class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic details;

  ApiException(this.message, {this.statusCode, this.details});

  @override
  String toString() => message;
}

class UnauthorizedException extends ApiException {
  UnauthorizedException([String message = 'Session expired or invalid credentials. Please log in again.'])
      : super(message, statusCode: 401);
}

class ForbiddenException extends ApiException {
  ForbiddenException([String message = 'You do not have permission to perform this action.'])
      : super(message, statusCode: 403);
}

class NotFoundException extends ApiException {
  NotFoundException([String message = 'Requested resource not found.'])
      : super(message, statusCode: 404);
}

class ValidationException extends ApiException {
  ValidationException(String message, {dynamic details})
      : super(message, statusCode: 422, details: details);
}

class NetworkException extends ApiException {
  NetworkException([String message = 'Unable to connect to server. Please check your internet connection or server status.'])
      : super(message);
}

class TimeoutException extends ApiException {
  TimeoutException([String message = 'Request timed out. Please try again.'])
      : super(message);
}
