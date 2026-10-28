/**
 * Pingo Popup Event Service
 * Singleton event bus for triggering Pingo Mascot status and download notifications
 * across all React components, hooks, and non-React utility functions.
 */

// Custom event identifier
export const PINGO_POPUP_EVENT = 'pingo:popup:trigger';

// Supported Pingo Poses (from brand mascot package)
export const PINGO_POSES = {
  WALK: 'walk',
  ACTION: 'action',
  RUN: 'run',
  KICK: 'kick',
  IDEA: 'idea',
  VICTORY: 'victory',
  PLAYFUL: 'playful',
  SALUTE: 'salute',
  POINT_RIGHT: 'point-right',
  INSPECT: 'inspect',
  POINT_SIDE: 'point-side',
  CELEBRATE: 'celebrate',
};

// Anti-duplicate tracker
let lastEventSignature = null;
let lastEventTimestamp = 0;
const DEDUPLICATION_COOLDOWN_MS = 1400;

class PingoPopupService {
  /**
   * Dispatches a popup event safely with de-duplication.
   */
  static trigger(options = {}) {
    if (typeof window === 'undefined') return;

    const {
      type = 'status',              // 'status' | 'download' | 'celebrate' | 'info'
      pose = PINGO_POSES.SALUTE,
      title = 'Action Completed',
      subtitle = '',
      badge = 'UPDATED',
      reference = '',
      duration = 3800,
      sound = true,
      theme = 'default'             // 'default' | 'success' | 'celebrate' | 'primary' | 'download'
    } = options;

    // De-duplication check: prevents double-clicks, rapid API responses, and React re-renders
    const signature = `${type}_${pose}_${title}_${reference}_${badge}`;
    const now = Date.now();
    if (lastEventSignature === signature && (now - lastEventTimestamp) < DEDUPLICATION_COOLDOWN_MS) {
      return;
    }
    lastEventSignature = signature;
    lastEventTimestamp = now;

    const detail = {
      id: `pingo_${now}_${Math.random().toString(36).substr(2, 6)}`,
      type,
      pose,
      title,
      subtitle,
      badge,
      reference,
      duration,
      sound,
      theme,
      timestamp: now
    };

    const event = new CustomEvent(PINGO_POPUP_EVENT, { detail });
    window.dispatchEvent(event);
  }

  /**
   * Helper: Trigger Status Update Popup
   * Automatically maps common CRM statuses to the corresponding Pingo pose and theme.
   */
  static triggerStatusUpdate({
    module = 'Lead',              // 'Lead' | 'Deal' | 'Quotation' | 'Proforma' | 'Invoice' | 'Payment' | 'Support' | 'Onboarding'
    status = 'UPDATED',
    reference = '',               // e.g. 'Lead #102', 'QT-001', 'PI-004'
    customMessage = '',
    customPose = null
  }) {
    const normStatus = String(status || '').toUpperCase().trim();
    let pose = customPose || PINGO_POSES.ACTION;
    let title = `${module} Status Updated`;
    let subtitle = customMessage || `Successfully marked as ${normStatus}`;
    let badge = normStatus;
    let theme = 'success';

    // 1. Deal WON / Converted
    if (normStatus === 'WON' || normStatus === 'DEAL WON') {
      pose = PINGO_POSES.CELEBRATE;
      title = '🏆 Deal Marked as WON!';
      subtitle = customMessage || `${reference || 'Deal'} successfully closed and handed off!`;
      badge = 'DEAL WON';
      theme = 'celebrate';
    } else if (normStatus === 'LOST') {
      pose = PINGO_POSES.KICK;
      title = `${module} Marked as Lost`;
      subtitle = customMessage || `${reference || 'Record'} closed as lost.`;
      badge = 'CLOSED LOST';
      theme = 'default';
    } else if (normStatus === 'CONVERTED') {
      pose = PINGO_POSES.VICTORY;
      title = '🌟 Converted to Customer!';
      subtitle = customMessage || `${reference || 'Lead'} successfully converted.`;
      badge = 'CONVERTED';
      theme = 'celebrate';
    } 
    // 2. Proposal / Quotation / Proforma / Invoice
    else if (normStatus === 'PROPOSAL SENT' || normStatus === 'PROPOSAL') {
      pose = PINGO_POSES.POINT_RIGHT;
      title = '💼 Proposal / Quotation Sent';
      badge = 'PROPOSAL SENT';
      theme = 'primary';
    } else if (normStatus === 'ISSUED') {
      pose = PINGO_POSES.SALUTE;
      title = `📄 ${module} Issued!`;
      subtitle = customMessage || `${reference || 'Document'} is now officially issued.`;
      badge = 'ISSUED';
      theme = 'primary';
    } 
    // 3. Payment Statuses
    else if (normStatus === 'PAID' || normStatus === 'PAYMENT CONFIRMED') {
      pose = PINGO_POSES.CELEBRATE;
      title = '💳 Payment Verified & Confirmed!';
      subtitle = customMessage || `${reference || 'Payment'} confirmed. Onboarding is authorized.`;
      badge = 'PAID IN FULL';
      theme = 'celebrate';
    } else if (normStatus === 'PARTIAL') {
      pose = PINGO_POSES.ACTION;
      title = '💳 Partial Payment Recorded';
      badge = 'PARTIAL PAYMENT';
      theme = 'primary';
    } 
    // 4. Support & Onboarding Stages
    else if (normStatus === 'COMPLETED' || normStatus === 'ONBOARDING COMPLETED') {
      pose = PINGO_POSES.CELEBRATE;
      title = '🎉 Onboarding Completed!';
      subtitle = customMessage || `${reference || 'Customer'} is fully activated and onboarded.`;
      badge = 'COMPLETED';
      theme = 'celebrate';
    } else if (normStatus === 'ONBOARDING_IN_PROGRESS' || normStatus === 'IN PROGRESS') {
      pose = PINGO_POSES.RUN;
      title = '⚙️ Onboarding In Progress';
      subtitle = customMessage || `Customer training and deployment active for ${reference}.`;
      badge = 'IN PROGRESS';
      theme = 'primary';
    } else if (normStatus === 'PENDING_ONBOARDING') {
      pose = PINGO_POSES.WALK;
      title = '🚀 Client Queued for Onboarding';
      badge = 'ONBOARDING QUEUED';
      theme = 'primary';
    } 
    // 5. Follow-ups
    else if (normStatus.includes('FOLLOW')) {
      pose = PINGO_POSES.RUN;
      title = '⏰ Follow-Up Scheduled';
      subtitle = customMessage || `Reminder set for ${reference || 'lead'}.`;
      badge = 'FOLLOW-UP';
      theme = 'primary';
    } else if (normStatus === 'CONTACTED') {
      pose = PINGO_POSES.ACTION;
      title = '📞 Lead Contacted';
      subtitle = customMessage || `Outreach logged for ${reference || 'lead'}.`;
      badge = 'CONTACTED';
      theme = 'success';
    } else if (normStatus === 'QUALIFIED') {
      pose = PINGO_POSES.IDEA;
      title = '💡 Lead Qualified';
      subtitle = customMessage || `${reference || 'Lead'} verified as qualified opportunity.`;
      badge = 'QUALIFIED';
      theme = 'primary';
    }

    this.trigger({
      type: 'status',
      pose,
      title,
      subtitle,
      badge,
      reference,
      theme
    });
  }

  /**
   * Helper: Trigger Document / File Download Success Popup
   */
  static triggerDownloadSuccess({
    docType = 'Document',        // 'Quotation' | 'Proforma' | 'Tax Invoice' | 'Report' | 'Excel' | 'Export'
    fileName = '',
    reference = '',
    customMessage = '',
    customPose = null
  }) {
    const normType = String(docType || '').toLowerCase();
    let pose = customPose || PINGO_POSES.SALUTE;
    let title = `${docType} Downloaded`;
    let badge = 'DOWNLOADED';
    let theme = 'download';

    if (normType.includes('tax invoice') || normType === 'invoice') {
      pose = PINGO_POSES.CELEBRATE;
      title = '🧾 Statutory Tax Invoice Downloaded';
      badge = 'TAX INVOICE';
      theme = 'celebrate';
    } else if (normType.includes('proforma')) {
      pose = PINGO_POSES.SALUTE;
      title = '📑 Proforma Invoice Downloaded';
      badge = 'PROFORMA';
      theme = 'primary';
    } else if (normType.includes('quotation')) {
      pose = PINGO_POSES.SALUTE;
      title = '📄 Official Quotation PDF Downloaded';
      badge = 'QUOTATION';
      theme = 'primary';
    } else if (normType.includes('excel') || normType.includes('sheet') || normType.includes('report') || normType.includes('csv')) {
      pose = PINGO_POSES.POINT_RIGHT;
      title = '📊 Spreadsheet Report Exported';
      badge = 'EXCEL / CSV';
      theme = 'success';
    }

    const subtitle = customMessage || (fileName ? `Saved as ${fileName}` : 'File saved to your Downloads folder.');

    this.trigger({
      type: 'download',
      pose,
      title,
      subtitle,
      badge,
      reference: reference || fileName,
      theme
    });
  }

  /**
   * Helper: Show standard notification or toast via PingoPopup
   */
  static showNotification({
    title = 'Success',
    message = '',
    subtitle = '',
    type = 'success',
    badge = null,
    duration = 3800
  } = {}) {
    let theme = 'default';
    let pose = PINGO_POSES.SALUTE;
    let badgeText = badge || (type === 'error' ? 'ERROR' : type === 'warning' ? 'ALERT' : 'SUCCESS');

    if (type === 'success') {
      theme = 'success';
      pose = PINGO_POSES.VICTORY;
    } else if (type === 'celebrate') {
      theme = 'celebrate';
      pose = PINGO_POSES.CELEBRATE;
    } else if (type === 'error') {
      theme = 'default';
      pose = PINGO_POSES.INSPECT;
    }

    this.trigger({
      type: 'status',
      pose,
      title,
      subtitle: message || subtitle,
      badge: badgeText,
      theme,
      duration
    });
  }
}

export default PingoPopupService;
