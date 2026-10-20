/**
 * Helper utility for consistent DD/MM/YYYY date and 12-hour time formatting across WaCRM.
 * Guaranteed Asia/Kolkata (IST) timezone consistency.
 */

const MONTH_NAMES_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

/**
 * Formats a date string or Date object into DD/MM/YYYY format.
 * Examples: 
 *   "2026-09-25" -> "25/09/2026"
 *   "2026-09-28" -> "28/09/2026"
 */
export const formatDateDDMMYYYY = (dateStr) => {
  if (!dateStr) return '-';
  
  // Direct YYYY-MM-DD parsing to avoid timezone shifts
  if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
    const parts = dateStr.split('T')[0].split('-');
    if (parts.length === 3) {
      const [year, month, day] = parts;
      return `${day.padStart(2, '0')}/${month.padStart(2, '0')}/${year}`;
    }
  }

  try {
    const parseableStr = (typeof dateStr === 'string' && dateStr.includes('T') && !dateStr.endsWith('Z') && !dateStr.includes('+')) 
      ? dateStr + 'Z' 
      : dateStr;
    const d = new Date(parseableStr);
    if (isNaN(d.getTime())) return String(dateStr);
    
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    return `${day}/${month}/${year}`;
  } catch (e) {
    return String(dateStr);
  }
};

/**
 * Formats a time string into 12-hour AM/PM format.
 * Examples:
 *   "11:30" -> "11:30 AM"
 *   "14:30" -> "02:30 PM"
 *   "11:30 AM" -> "11:30 AM"
 */
export const formatTime12Hour = (timeStr) => {
  if (!timeStr) return '10:00 AM';
  const str = String(timeStr).trim();
  if (/am|pm/i.test(str)) return str;

  const parts = str.split(':');
  if (parts.length >= 2) {
    let hours = parseInt(parts[0], 10);
    const minutes = parts[1].padStart(2, '0');
    if (!isNaN(hours)) {
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12;
      hours = hours ? hours : 12;
      const formattedHours = String(hours).padStart(2, '0');
      return `${formattedHours}:${minutes} ${ampm}`;
    }
  }
  return str;
};

/**
 * Formats a Lead Received timestamp strictly into Asia/Kolkata (IST) display format:
 *   Date: 08 Oct 2026
 *   Time: 12:35 PM
 *   Full: 08 Oct 2026, 12:35 PM
 *
 * Robustly parses both database naive IST datetime strings (e.g. "2026-10-08 12:35:00")
 * and ISO strings (e.g. "2026-10-08T12:35:00" or UTC with 'Z').
 */
export const formatLeadReceived = (dateStr) => {
  if (!dateStr) {
    return { date: '-', time: '-', full: '-' };
  }

  const str = String(dateStr).trim();

  // 1. Direct Regex match on standard DB formats: YYYY-MM-DD HH:mm:ss or YYYY-MM-DDTHH:mm:ss
  // (stored as IST in database, avoiding browser timezone shifting)
  const dbMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (dbMatch && !str.endsWith('Z') && !str.includes('+')) {
    const [, year, month, day, hoursStr, minutesStr] = dbMatch;
    const monthNum = parseInt(month, 10);
    const monthName = MONTH_NAMES_SHORT[monthNum - 1] || month;
    let hours = parseInt(hoursStr, 10);
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    const formattedHours = String(hours).padStart(2, '0');
    const formattedDate = `${day.padStart(2, '0')} ${monthName} ${year}`;
    const formattedTime = `${formattedHours}:${minutesStr} ${ampm}`;

    return {
      date: formattedDate,
      time: formattedTime,
      full: `${formattedDate}, ${formattedTime}`
    };
  }

  // 2. ISO with UTC/offset -> Convert strictly to Asia/Kolkata (IST)
  try {
    const d = new Date(str);
    if (isNaN(d.getTime())) {
      return { date: String(dateStr), time: '', full: String(dateStr) };
    }

    const options = {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    };

    const parts = new Intl.DateTimeFormat('en-GB', options).formatToParts(d);
    const getPart = (type) => parts.find(p => p.type === type)?.value || '';

    const day = getPart('day');
    const month = getPart('month');
    const year = getPart('year');
    const hour = getPart('hour');
    const minute = getPart('minute');
    const dayPeriod = getPart('dayPeriod').toUpperCase();

    const formattedDate = `${day} ${month} ${year}`;
    const formattedTime = `${hour}:${minute} ${dayPeriod}`;

    return {
      date: formattedDate,
      time: formattedTime,
      full: `${formattedDate}, ${formattedTime}`
    };
  } catch (err) {
    return { date: String(dateStr), time: '', full: String(dateStr) };
  }
};

export const formatLeadReceivedDate = (dateStr) => formatLeadReceived(dateStr).date;
export const formatLeadReceivedTime = (dateStr) => formatLeadReceived(dateStr).time;
export const formatLeadReceivedFull = (dateStr) => formatLeadReceived(dateStr).full;

/**
 * Parses timestamps and formats them into DD Mon YYYY, hh:mm AM/PM in Asia/Kolkata (IST) timezone.
 */
export const formatLocalDateTime = (isoStr) => {
  if (!isoStr) return '-';
  try {
    const res = formatLeadReceived(isoStr);
    if (res && res.full && res.full !== '-') {
      return res.full;
    }
    return String(isoStr);
  } catch (e) {
    return String(isoStr);
  }
};
