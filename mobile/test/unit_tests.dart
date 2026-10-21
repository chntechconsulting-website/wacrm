import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/constants/api_endpoints.dart';
import 'package:mobile/core/network/api_exceptions.dart';
import 'package:mobile/core/widgets/pingo_mascot_widget.dart';
import 'package:mobile/features/activities/models/activity_model.dart';
import 'package:mobile/features/auth/models/user_model.dart';
import 'package:mobile/features/field_visits/models/field_visit_model.dart';
import 'package:mobile/features/followups/models/followup_model.dart';
import 'package:mobile/features/quotations/models/quotation_model.dart';

void main() {
  group('Role-Based Access Control (RBAC) & User Hierarchy Tests', () {
    test('Admin role permissions', () {
      final user = UserModel(
        id: 1,
        username: 'admin',
        role: 'ADMIN',
        name: 'System Admin',
        email: 'admin@company.com',
        status: 'ACTIVE',
        isActive: true,
      );

      expect(user.isAdmin, isTrue);
      expect(user.canViewSales, isTrue);
      expect(user.canViewSupport, isTrue);
      expect(user.canViewFinance, isTrue);
      expect(user.canManageUsers, isTrue);
      expect(user.canDeleteLeads, isTrue);
    });

    test('Sales Executive role permissions', () {
      final user = UserModel(
        id: 9,
        username: 'chnm040',
        role: 'SALES_EXECUTIVE',
        name: 'Sales Rep',
        email: 'rep@company.com',
        status: 'ACTIVE',
        isActive: true,
        reportingManagerId: 8,
      );

      expect(user.isAdmin, isFalse);
      expect(user.isSalesExecutive, isTrue);
      expect(user.canViewSales, isTrue);
      expect(user.canViewSupport, isFalse);
      expect(user.canViewFinance, isFalse);
      expect(user.canManageUsers, isFalse);
      expect(user.canDeleteLeads, isFalse);
    });

    test('Support Executive role permissions', () {
      final user = UserModel(
        id: 10,
        username: 'chnm023',
        role: 'SUPPORT_EXECUTIVE',
        name: 'Support Agent',
        email: 'support@company.com',
        status: 'ACTIVE',
        isActive: true,
        reportingManagerId: 11,
      );

      expect(user.isAdmin, isFalse);
      expect(user.isSupportExecutive, isTrue);
      expect(user.canViewSales, isFalse);
      expect(user.canViewSupport, isTrue);
      expect(user.canViewFinance, isFalse);
    });

    test('Finance role permissions', () {
      final user = UserModel(
        id: 15,
        username: 'finance_usr',
        role: 'FINANCE',
        name: 'Accountant',
        email: 'accounts@company.com',
        status: 'ACTIVE',
        isActive: true,
      );

      expect(user.isFinance, isTrue);
      expect(user.canViewFinance, isTrue);
      expect(user.canViewSupport, isFalse);
    });
  });

  group('Pingo Mascot Status Mapping & Integration Tests', () {
    test('Pingo poses map accurately to CRM statuses', () {
      expect(PingoPoses.mapStatusToPose('WON'), equals(PingoPoses.celebrate));
      expect(PingoPoses.mapStatusToPose('CONVERTED'), equals(PingoPoses.celebrate));
      expect(PingoPoses.mapStatusToPose('QUALIFIED'), equals(PingoPoses.victory));
      expect(PingoPoses.mapStatusToPose('LOST'), equals(PingoPoses.kick));
      expect(PingoPoses.mapStatusToPose('FOLLOW_UP'), equals(PingoPoses.pointRight));
      expect(PingoPoses.mapStatusToPose('CONTACTED'), equals(PingoPoses.action));
      expect(PingoPoses.mapStatusToPose('NEW'), equals(PingoPoses.idea));
    });

    test('Pingo assets paths exist for all poses', () {
      for (final pose in [
        PingoPoses.salute,
        PingoPoses.celebrate,
        PingoPoses.victory,
        PingoPoses.kick,
        PingoPoses.idea,
        PingoPoses.pointRight,
        PingoPoses.pointSide,
        PingoPoses.action,
        PingoPoses.run,
        PingoPoses.walk,
        PingoPoses.inspect,
        PingoPoses.playful,
        PingoPoses.standingWelcome,
        PingoPoses.actionLanding,
        PingoPoses.celebrateSuccess,
        PingoPoses.targetVictory,
      ]) {
        final path = PingoPoses.getAssetPath(pose);
        expect(path, startsWith('assets/mascot/pingo-'));
        expect(path, endsWith('.png'));
      }
    });
  });

  group('Quotation & Website Sync Rule Enforcement Tests', () {
    test('Eligible WAHRMS proforma is permitted to synchronize', () {
      final proforma = QuotationModel(
        id: 101,
        docType: 'proforma',
        docNumber: 'PI-WAHRMS-001',
        customerName: 'Acme Software',
        status: 'issued',
        paymentStatus: 'unpaid',
        subtotal: 50000,
        taxTotal: 9000,
        grandTotal: 59000,
        productCategory: 'wahrms',
        taxMode: 'intra',
        lineItems: [],
      );

      expect(proforma.isEligibleForSync, isTrue);
    });

    test('CRITICAL RULE: Biometric proforma is blocked from website synchronization', () {
      final biometricDoc = QuotationModel(
        id: 102,
        docType: 'proforma',
        docNumber: 'PI-BIO-002',
        customerName: 'Hardware Client',
        status: 'issued',
        paymentStatus: 'unpaid',
        subtotal: 25000,
        taxTotal: 4500,
        grandTotal: 29500,
        productCategory: 'biometric',
        taxMode: 'intra',
        lineItems: [],
      );

      expect(biometricDoc.isEligibleForSync, isFalse);
    });
  });

  group('API Exception Mapping Tests', () {
    test('Exception hierarchy and status codes', () {
      final unauth = UnauthorizedException();
      expect(unauth.statusCode, equals(401));

      final forbidden = ForbiddenException();
      expect(forbidden.statusCode, equals(403));

      final notFound = NotFoundException();
      expect(notFound.statusCode, equals(404));

      final valErr = ValidationException('Invalid input', details: {'field': 'required'});
      expect(valErr.statusCode, equals(422));
      expect(valErr.details, isNotNull);
    });
  });

  group('Production Backend Endpoints & WhatsApp Tests', () {
    test('Default base URL targets production wapluscrm.in', () {
      expect(ApiEndpoints.productionBaseUrl, equals('https://www.wapluscrm.in'));
      expect(ApiEndpoints.baseUrl, equals('https://www.wapluscrm.in'));
      expect(ApiEndpoints.apiPrefix, equals('https://www.wapluscrm.in/api'));
      expect(ApiEndpoints.login, equals('https://www.wapluscrm.in/api/auth/login'));
      expect(ApiEndpoints.me, equals('https://www.wapluscrm.in/api/auth/me'));
      expect(ApiEndpoints.leads, equals('https://www.wapluscrm.in/api/leads'));
      expect(ApiEndpoints.dashboardStats, equals('https://www.wapluscrm.in/api/reports/dashboard'));
      expect(ApiEndpoints.followups, equals('https://www.wapluscrm.in/api/followups'));
      expect(ApiEndpoints.customers, equals('https://www.wapluscrm.in/api/customers'));
      expect(ApiEndpoints.manualCall, equals('https://www.wapluscrm.in/api/ivr/manual-call'));
      expect(ApiEndpoints.initiateCall, equals('https://www.wapluscrm.in/api/ivr/call'));
      expect(ApiEndpoints.whatsappConversations, equals('https://www.wapluscrm.in/api/whatsapp/conversations'));
      expect(ApiEndpoints.whatsappSendMessage, equals('https://www.wapluscrm.in/api/whatsapp/send-message'));
    });

    test('Field Visit endpoints and serialization', () {
      expect(ApiEndpoints.fieldVisits, equals('https://www.wapluscrm.in/api/field-visits'));
      expect(ApiEndpoints.fieldVisitById(42), equals('https://www.wapluscrm.in/api/field-visits/42'));
      expect(ApiEndpoints.employeeFieldVisits(7), equals('https://www.wapluscrm.in/api/employee-monitoring/7/field-visits'));

      final visit = FieldVisitModel.fromJson({
        'id': 10,
        'employee_id': 3,
        'employee_name': 'Karthik Raja',
        'lead_id': 55,
        'customer_name': 'Apex Retail Hub',
        'checkin_time': '2026-10-21T11:00:00Z',
        'checkin_lat': '13.0827',
        'checkin_lng': '80.2707',
        'checkin_address': 'Anna Salai, Chennai',
        'photo_url': 'https://storage.wapluscrm.in/board.jpg',
        'visiting_card_url': 'https://storage.wapluscrm.in/card.jpg',
        'customer_requirements': '500 units biometrics with attendance software',
        'visit_outcome': 'Interested',
        'notes': 'Met with MD, highly interested in enterprise bundle.',
        'status': 'COMPLETED',
        'client_token': 'visit_tok_99182',
        'followup_id': 88,
        'followup': {
          'id': 88,
          'followup_date': '2026-10-23',
          'followup_time': '11:00 AM',
          'priority': 'HIGH',
          'status': 'Pending'
        }
      });

      expect(visit.id, equals(10));
      expect(visit.employeeName, equals('Karthik Raja'));
      expect(visit.customerName, equals('Apex Retail Hub'));
      expect(visit.checkinLat, equals('13.0827'));
      expect(visit.visitOutcome, equals('Interested'));
      expect(visit.clientToken, equals('visit_tok_99182'));
      expect(visit.followupId, equals(88));
      expect(visit.followup!['followup_date'], equals('2026-10-23'));

      final jsonMap = visit.toJson();
      expect(jsonMap['customer_name'], equals('Apex Retail Hub'));
      expect(jsonMap['client_token'], equals('visit_tok_99182'));
    });

    test('Automatic CRM Activity and Follow-up model integration', () {
      final act = ActivityModel.fromJson({
        'id': 105,
        'lead_id': 55,
        'lead_name': 'Apex Retail Hub',
        'employee_id': 3,
        'employee_name': 'Karthik Raja',
        'activity_type': 'FIELD_VISIT',
        'description': 'Field Visit completed for Apex Retail Hub.\nOutcome: Interested\nLocation: Anna Salai, Chennai\nRequirements: 500 units',
        'created_at': '2026-10-21T11:05:00Z'
      });

      expect(act.activityType, equals('FIELD_VISIT'));
      expect(act.description, contains('Outcome: Interested'));
      expect(act.description, contains('Anna Salai'));

      final fu = FollowupModel.fromJson({
        'id': 88,
        'lead_id': 55,
        'lead_name': 'Apex Retail Hub',
        'lead_phone': '+919876543210',
        'assigned_to': 3,
        'followup_date': '2026-10-23',
        'followup_time': '11:00 AM',
        'priority': 'HIGH',
        'status': 'Pending',
        'notes': 'Follow-up after field visit: discussion on quotation.'
      });

      expect(fu.priority, equals('HIGH'));
      expect(fu.status, equals('Pending'));
      expect(fu.followupDate, equals('2026-10-23'));
      expect(fu.followupTime, equals('11:00 AM'));
    });
  });
}
