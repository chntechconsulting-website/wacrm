import React, { useState, useEffect } from 'react';
import { X, Download, ZoomIn, ZoomOut, RotateCw, FileText, CheckCircle, ExternalLink, RefreshCw } from 'lucide-react';
import { getPdfBlob, generateBillingPdf, generateQuotationPdf, generateProformaPdf, generatePoPdf, generateTaxInvoicePdf } from '../../utils/quotationPdf';
import PingoPopupService from '../../services/pingoPopupService';
import API from '../../services/api';

/**
 * Universal PDF Preview Modal for Quotations, Purchase Orders (PO), Proformas, and Tax Invoices.
 * 
 * Allows the user to inspect the exact rendered document layout, multiline item descriptions,
 * tax computation, terms, etc., before explicitly hitting "Download PDF".
 */
export default function DocumentPdfPreviewModal({
  isOpen,
  onClose,
  docData = null,
  title = 'Document Preview',
  onDownloadComplete = null
}) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let activeUrl = null;
    let isMounted = true;

    if (!isOpen || !docData) {
      setBlobUrl(null);
      setLoading(false);
      setError(null);
      return;
    }

    const loadPdfBlob = async () => {
      setLoading(true);
      setError(null);

      // Strategy 1: If document has an ID or server download endpoint, try fetching exact backend generated PDF if applicable
      const dType = (docData.docType || docData.doc_type || 'quotation').toLowerCase();
      const rawId = docData.id || docData.docId;
      const cleanId = rawId ? String(rawId).replace('local_', '').trim() : null;

      let fetchedBlob = null;

      if (cleanId && !String(cleanId).startsWith('PREVIEW') && !docData.isDraftPreview) {
        try {
          let endpoint;
          if (dType === 'invoice') {
            endpoint = `/integrations/waquote/invoices/${cleanId}/download`;
          } else if (dType === 'proforma') {
            endpoint = `/integrations/waquote/proformas/${cleanId}/download`;
          } else if (dType === 'po' || dType === 'purchase_order') {
            endpoint = `/integrations/waquote/quotations/${cleanId}/download`;
          } else {
            endpoint = `/integrations/waquote/quotations/${cleanId}/download`;
          }

          const res = await API.get(endpoint, { responseType: 'blob' });
          if (res.data && res.data.size > 500) {
            fetchedBlob = new Blob([res.data], { type: 'application/pdf' });
          }
        } catch (backendErr) {
          console.warn('Backend download endpoint not reachable for preview, generating client-side preview:', backendErr);
        }
      }

      // Strategy 2: If no server blob, generate client-side with pdfMake
      if (!fetchedBlob) {
        try {
          fetchedBlob = await getPdfBlob(docData);
        } catch (clientErr) {
          console.error('Failed to generate client-side PDF blob for preview:', clientErr);
          if (isMounted) {
            setError(clientErr.message || 'Failed to render PDF preview.');
            setLoading(false);
          }
          return;
        }
      }

      if (isMounted && fetchedBlob) {
        activeUrl = window.URL.createObjectURL(fetchedBlob);
        setBlobUrl(activeUrl);
        setLoading(false);
      }
    };

    loadPdfBlob();

    return () => {
      isMounted = false;
      if (activeUrl) {
        window.URL.revokeObjectURL(activeUrl);
      }
    };
  }, [isOpen, docData]);

  if (!isOpen || !docData) return null;

  const dType = (docData.docType || docData.doc_type || 'quotation').toLowerCase();
  const isInvoice = dType === 'invoice';
  const isProforma = dType === 'proforma';
  const isPO = dType === 'po' || dType === 'purchase_order';

  const docLabel = isInvoice 
    ? 'Tax Invoice' 
    : isProforma 
    ? 'Proforma Invoice' 
    : isPO 
    ? 'Purchase Order (PO)' 
    : 'Quotation';

  const docNumber = docData.number || docData.doc_number || docData.docNumber || 'DOC';
  const cleanDocNum = String(docNumber).replace(/[\\/]/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');

  const getFilename = () => {
    if (isInvoice) return `Tax_Invoice_${cleanDocNum}.pdf`;
    if (isProforma) return `Proforma_Invoice_${cleanDocNum}.pdf`;
    if (isPO) return `Purchase_Order_${cleanDocNum}.pdf`;
    return `Quotation_${cleanDocNum}.pdf`;
  };

  const handleDownload = () => {
    try {
      setDownloading(true);
      if (blobUrl) {
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = getFilename();
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        // Fallback to direct download
        if (isInvoice) {
          generateTaxInvoicePdf(docData, true);
        } else if (isProforma) {
          generateProformaPdf(docData, true);
        } else if (isPO) {
          generatePoPdf(docData, true);
        } else {
          generateQuotationPdf(docData, true);
        }
      }

      PingoPopupService.triggerDownloadSuccess({
        docType: docLabel,
        reference: docNumber,
        customMessage: `${docLabel} ${docNumber} downloaded successfully!`
      });

      if (onDownloadComplete) {
        onDownloadComplete();
      }
    } catch (err) {
      console.error('Download error:', err);
    } finally {
      setDownloading(false);
    }
  };

  const openInNewTab = () => {
    if (blobUrl) {
      window.open(blobUrl, '_blank');
    }
  };

  const primaryColor = isInvoice ? '#1e40af' : '#dc2626';

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5"
      style={{
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(4px)',
        animation: 'fadeIn 0.2s ease-out'
      }}
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl flex flex-col w-full max-w-5xl overflow-hidden"
        style={{
          height: '92vh',
          border: '1px solid #cbd5e1'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div 
          className="flex items-center justify-between px-5 py-3.5 border-b"
          style={{
            background: isInvoice 
              ? 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)' 
              : 'linear-gradient(135deg, #991b1b 0%, #dc2626 100%)',
            color: '#ffffff'
          }}
        >
          <div className="flex items-center gap-3">
            <div 
              className="p-2 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(255, 255, 255, 0.2)' }}
            >
              <FileText size={20} className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-wide leading-tight">
                  {docLabel} Preview
                </h3>
                <span 
                  className="px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider"
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.25)',
                    color: '#ffffff'
                  }}
                >
                  #{docNumber}
                </span>
              </div>
              <p className="text-xs text-white/80 mt-0.5">
                Review the document formatting and line item breakdown before downloading
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {blobUrl && (
              <button
                type="button"
                onClick={openInNewTab}
                className="btn btn-sm text-white/90 hover:text-white flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition"
                style={{
                  background: 'rgba(255, 255, 255, 0.15)',
                  border: '1px solid rgba(255, 255, 255, 0.25)',
                  fontSize: '0.8rem'
                }}
                title="Open PDF in a new browser tab"
              >
                <ExternalLink size={14} /> Open in Tab
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="text-white/80 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition"
              title="Close Preview"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* PDF Viewer Body */}
        <div 
          className="flex-1 bg-slate-100 flex items-center justify-center relative overflow-hidden"
          style={{ minHeight: '300px' }}
        >
          {loading && (
            <div className="flex flex-col items-center justify-center gap-3 text-slate-600">
              <RefreshCw size={32} className="animate-spin text-slate-400" />
              <p className="text-sm font-medium">Generating pixel-perfect PDF preview...</p>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center gap-3 text-center p-6 max-w-md">
              <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center font-bold text-xl">!</div>
              <h4 className="text-sm font-bold text-slate-800">Preview Generation Issue</h4>
              <p className="text-xs text-slate-600 leading-relaxed">{error}</p>
              <button
                type="button"
                onClick={handleDownload}
                className="btn btn-sm btn-primary mt-2 flex items-center gap-1.5"
                style={{ backgroundColor: primaryColor }}
              >
                <Download size={14} /> Download Document Directly
              </button>
            </div>
          )}

          {!loading && !error && blobUrl && (
            <iframe
              src={`${blobUrl}#toolbar=0&navpanes=0&scrollbar=1&view=FitH`}
              title={`${docLabel} Preview`}
              className="w-full h-full border-0"
              style={{ display: 'block', backgroundColor: '#525659' }}
            />
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-5 py-3 bg-white border-t border-slate-200">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <CheckCircle size={14} className="text-emerald-600" />
            <span>Format: Official High-Resolution Vector PDF • Ready for client dispatch</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary px-4 py-2 text-xs font-medium rounded-lg text-slate-700 bg-slate-100 hover:bg-slate-200 transition"
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={loading || downloading}
              className="btn flex items-center gap-2 px-5 py-2 text-xs font-semibold rounded-lg text-white shadow-sm transition hover:opacity-95"
              style={{
                backgroundColor: primaryColor,
                borderColor: primaryColor
              }}
            >
              <Download size={15} />
              {downloading ? 'Preparing Download...' : `Download ${docLabel}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
