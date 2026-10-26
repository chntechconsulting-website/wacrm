import React, { useState, useEffect } from 'react';
import { X, Download, FileText, CheckCircle, ExternalLink, RefreshCw } from 'lucide-react';
import { getPdfBlob, generateQuotationPdf, generateProformaPdf, generatePoPdf, generateTaxInvoicePdf } from '../../utils/quotationPdf';
import PingoPopupService from '../../services/pingoPopupService';
import API from '../../services/api';

/**
 * Universal PDF Preview Modal for Quotations, Purchase Orders (PO), Proformas, and Tax Invoices.
 * Uses robust inline styling and verified PDF blob generation so it renders reliably across all screen sizes.
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

      const dType = (docData.docType || docData.doc_type || 'quotation').toLowerCase();
      const rawId = docData.id || docData.docId;
      const cleanId = rawId ? String(rawId).replace('local_', '').trim() : null;

      let fetchedBlob = null;

      // Strategy 1: If document has a valid server ID and is not draft preview, try server download
      if (cleanId && !String(cleanId).startsWith('DRAFT') && !String(cleanId).startsWith('PREVIEW') && !docData.isDraftPreview) {
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

      // Strategy 2: Client-side vector generation with pdfMake
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

  const primaryColor = isInvoice ? '#1e3a8a' : '#dc2626';

  return (
    <div 
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(4px)',
        zIndex: 100000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px'
      }}
      onClick={onClose}
    >
      <div 
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          display: 'flex',
          flexDirection: 'column',
          width: '94vw',
          maxWidth: '1080px',
          height: '92vh',
          maxHeight: '92vh',
          overflow: 'hidden',
          border: '1px solid #cbd5e1'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div 
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 20px',
            background: isInvoice 
              ? 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)' 
              : 'linear-gradient(135deg, #991b1b 0%, #dc2626 100%)',
            color: '#ffffff',
            flexShrink: 0
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div 
              style={{
                padding: '8px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(255, 255, 255, 0.2)'
              }}
            >
              <FileText size={20} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#ffffff', letterSpacing: '0.01em' }}>
                  {docLabel} Preview
                </span>
                <span 
                  style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    backgroundColor: 'rgba(255, 255, 255, 0.25)',
                    color: '#ffffff'
                  }}
                >
                  #{docNumber}
                </span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'rgba(255, 255, 255, 0.85)', marginTop: '2px' }}>
                Review document formatting, item details and taxes before downloading
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {blobUrl && (
              <button
                type="button"
                onClick={openInNewTab}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  background: 'rgba(255, 255, 255, 0.18)',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  color: '#ffffff',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
                title="Open PDF in a new browser tab"
              >
                <ExternalLink size={14} /> Open in Tab
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.15)',
                border: 'none',
                borderRadius: '6px',
                color: '#ffffff',
                padding: '6px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              title="Close Preview"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* PDF Viewer Body */}
        <div 
          style={{
            flex: 1,
            backgroundColor: '#525659',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            overflow: 'hidden',
            minHeight: '200px'
          }}
        >
          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: '#f8fafc' }}>
              <RefreshCw size={32} className="spinning" style={{ color: '#94a3b8' }} />
              <div style={{ fontSize: '0.88rem', fontWeight: 500 }}>Generating pixel-perfect PDF preview...</div>
            </div>
          )}

          {error && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', textAlign: 'center', padding: '24px', maxWidth: '450px', backgroundColor: '#ffffff', borderRadius: '12px', margin: '20px' }}>
              <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: '#fee2e2', color: '#dc2626', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '1.25rem' }}>!</div>
              <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#0f172a' }}>Preview Generation Issue</div>
              <div style={{ fontSize: '0.78rem', color: '#64748b', lineHeight: 1.5 }}>{error}</div>
              <button
                type="button"
                onClick={handleDownload}
                className="btn btn-primary"
                style={{ backgroundColor: primaryColor, borderColor: primaryColor, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', marginTop: '6px' }}
              >
                <Download size={14} /> Download Document Directly
              </button>
            </div>
          )}

          {!loading && !error && blobUrl && (
            <iframe
              src={`${blobUrl}#toolbar=1&navpanes=0&scrollbar=1&view=FitH`}
              title={`${docLabel} Preview`}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                display: 'block',
                backgroundColor: '#525659'
              }}
            />
          )}
        </div>

        {/* Footer Actions */}
        <div 
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            backgroundColor: '#ffffff',
            borderTop: '1px solid #e2e8f0',
            flexShrink: 0
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: '#64748b' }}>
            <CheckCircle size={14} color="#16a34a" />
            <span>Format: Official High-Resolution Vector PDF</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              style={{ padding: '8px 16px', fontSize: '0.82rem' }}
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={loading || downloading}
              className="btn btn-primary"
              style={{
                backgroundColor: primaryColor,
                borderColor: primaryColor,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 20px',
                fontSize: '0.82rem',
                fontWeight: 600
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
