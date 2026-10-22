import 'package:flutter/material.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';

class PrivacyPolicyScreen extends StatelessWidget {
  const PrivacyPolicyScreen({super.key});

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
          'Privacy Policy',
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
                  colors: [Color(0xFF064E3B), Color(0xFF047857)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF064E3B).withValues(alpha: 0.25),
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
                          'WA!CRM Enterprise Privacy Policy',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Data Security & Protection Standards • CHN Technologies',
                          style: TextStyle(fontSize: 12, color: Color(0xFFA7F3D0)),
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
              title: 'Information We Collect',
              content:
                  'WA!CRM collects information required to deliver enterprise CRM services, including: employee user account details (name, username, department, email, phone number), client and lead records (names, phone numbers, email addresses, company names, requirements, notes), call interaction metadata (call durations, timestamps, employee extensions, recording URLs), and device diagnostic telemetry.',
            ),
            _buildSection(
              number: '2',
              title: 'How Information is Utilized',
              content:
                  'Data collected is used exclusively for: managing sales pipelines and support ticket lifecycles; executing automated and manual customer follow-ups; generating commercial quotations and official tax invoices; facilitating WhatsApp and voice interactions via authorized channels; and auditing organizational compliance.',
            ),
            _buildSection(
              number: '3',
              title: 'Role-Based Data Scoping',
              content:
                  'WA!CRM strictly isolates customer data according to enterprise Role-Based Access Control (RBAC). Sales Executives only access leads and calls assigned to them; Sales Managers access their supervised team members; Support personnel only view assigned support tickets; and organizational administrators govern system-wide records.',
            ),
            _buildSection(
              number: '4',
              title: 'Telephony & WhatsApp Integration',
              content:
                  'Voice call routing is processed via secure PBX/IVR partners (including Doocti). WhatsApp conversations utilize official Meta WhatsApp Cloud API endpoints. Message content, call logs, and attachments are processed strictly within your organization\'s dedicated environment and are never sold to external third-party advertisers.',
            ),
            _buildSection(
              number: '5',
              title: 'Industry-Standard Encryption & Storage',
              content:
                  'All data transmitted between the WA!CRM mobile application and the FastAPI server is encrypted using TLS 1.3 / SSL. Stored passwords utilize salted cryptographic hashes (bcrypt). Sensitive database records are hosted on secure enterprise cloud infrastructure with continuous automated backups.',
            ),
            _buildSection(
              number: '6',
              title: 'Data Retention & Deletion Policies',
              content:
                  'Customer records and audit trails are retained for as long as your enterprise subscription remains active, or as required by applicable tax and commercial accounting regulations. Enterprise administrators may request permanent purging or export of lead archives via official support channels.',
            ),
            _buildSection(
              number: '7',
              title: 'Third-Party Disclosures',
              content:
                  'We do not sell, rent, or lease your CRM database. Data is shared strictly with essential service infrastructure providers (such as Meta for WhatsApp messaging, Doocti for telephony, and secure AWS/Cloud hosting facilities) necessary to execute core business workflows.',
            ),
            _buildSection(
              number: '8',
              title: 'Privacy Rights & Contact',
              content:
                  'Users have the right to request access to their recorded personal details, request correction of inaccurate profile data, or inquire regarding security safeguards. Inquiries should be directed to privacy@chntechnologies.com.',
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
                  Icon(Icons.security_rounded, color: Color(0xFF059669), size: 22),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Your Privacy is Our Priority',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF0F172A)),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'WA!CRM adheres to strict corporate data confidentiality and enterprise protection guidelines.',
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
                  color: Color(0xFF059669),
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
