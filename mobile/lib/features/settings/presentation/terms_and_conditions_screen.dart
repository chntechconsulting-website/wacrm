import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';

class TermsAndConditionsScreen extends StatelessWidget {
  const TermsAndConditionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF162A45)),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Terms & Conditions',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: Color(0xFF0F172A),
          ),
        ),
        centerTitle: false,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Banner
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF1E3A5F), Color(0xFF162A45)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF162A45).withValues(alpha: 0.2),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'WA!CRM Terms of Service',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Last updated: October 2026 • Enterprise Version 1.0',
                          style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                        ),
                      ],
                    ),
                  ),
                  PingoMascotWidget(pose: PingoPoses.salute, height: 50),
                ],
              ),
            ),
            const SizedBox(height: 18),

            _buildSection(
              number: '1',
              title: 'Acceptance of Terms',
              content:
                  'By accessing, logging in to, or using the WA!CRM mobile application and connected enterprise CRM platform provided by CHN Technologies, you confirm that you have read, understood, and agreed to be bound by these Terms and Conditions. If you do not agree to these terms, you must not use or access the application.',
            ),
            _buildSection(
              number: '2',
              title: 'Authorized Enterprise Use & User Accounts',
              content:
                  'Access to WA!CRM is granted exclusively to authorized personnel, employees, and contractors of the subscribing organization. You are responsible for maintaining the confidentiality of your username, password, and session credentials. Any activity conducted under your account is your organization\'s responsibility. Sharing credentials or bypassing role-based access control (RBAC) is strictly prohibited.',
            ),
            _buildSection(
              number: '3',
              title: 'WhatsApp Cloud API & Communication Policy',
              content:
                  'WA!CRM provides integration with official WhatsApp Cloud API and telephony providers (such as Doocti). Users must comply with WhatsApp Business Solution policies, anti-spam guidelines, and regional telecommunication regulations. Automated or manual messaging must only be initiated with prior opt-in consent from customers and prospective leads.',
            ),
            _buildSection(
              number: '4',
              title: 'Lead Management & Customer Data Integrity',
              content:
                  'All customer contacts, phone numbers, leads, inquiries, proforma invoices, and payment data recorded into WA!CRM remain the exclusive proprietary property of the subscribing organization. Users agree not to export, scrape, duplicate, or misuse CRM customer data for unauthorized commercial or personal endeavors.',
            ),
            _buildSection(
              number: '5',
              title: 'Role-Based Permissions & Audit Governance',
              content:
                  'All interactions, including status updates, employee reassignments, deal won conversions, proforma invoice generation, and call logs, are continuously logged with immutable audit timestamps, IP addresses, and user identifiers for enterprise compliance and organizational security.',
            ),
            _buildSection(
              number: '6',
              title: 'System Availability & Service Level Agreement',
              content:
                  'CHN Technologies endeavors to provide continuous 99.9% uptime for WA!CRM services. Scheduled maintenance, emergency security patches, or telecommunication network carrier outages may occasionally affect service availability. Off-line data caches synchronize automatically once connectivity is restored.',
            ),
            _buildSection(
              number: '7',
              title: 'Limitation of Liability',
              content:
                  'To the maximum extent permitted by applicable law, CHN Technologies and its affiliates shall not be liable for any indirect, incidental, special, or consequential damages resulting from unauthorized device access, carrier SMS/WhatsApp API outages, or improper employee data handling.',
            ),
            _buildSection(
              number: '8',
              title: 'Termination & Policy Modifications',
              content:
                  'We reserve the right to suspend or terminate account access for any user violating organizational policies, intellectual property rights, or system security integrity. Continued use of WA!CRM following any policy updates constitutes full acceptance of the revised terms.',
            ),

            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.headset_mic_outlined, color: AppColors.primary, size: 22),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Questions about our Terms?',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF0F172A)),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'Contact legal@chntechnologies.com or your CRM System Administrator.',
                          style: TextStyle(fontSize: 11.5, color: Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSection({
    required String number,
    required String title,
    required String content,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF1F5F9), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: const BoxDecoration(
                  color: Color(0xFFE5252A),
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(
                    number,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF0F172A),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            content,
            style: const TextStyle(
              fontSize: 12.5,
              color: Color(0xFF475569),
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}
