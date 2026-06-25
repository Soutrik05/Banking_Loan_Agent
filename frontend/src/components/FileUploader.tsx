import React, { useRef, useState, useEffect } from 'react';
import { uploadDocument, uploadPropertyDocument, getPropertyDocuments } from '../services/api';

interface FileUploaderProps {
  label: string;
  docType: string;
  /** KYC mode: applicant temp_id. Property mode: the customer's JWT token. */
  token: string;
  onUploaded?: (url: string) => void;
  /** Full backend response for this upload (extracted_fields, status, registration, ...). */
  onResult?: (data: any) => void;
  /** Allow selecting/dropping more than one file for this slot (e.g. 3 salary slips). */
  multiple?: boolean;
  /** 'kyc' (default): existing single-slot financial-document behaviour. 'property': 4-doc checklist uploaded to Supabase Storage. */
  mode?: 'kyc' | 'property';
  /** Required when mode === 'property'. */
  sessionId?: string;
}

const PROPERTY_DOC_TYPES: { docType: string; label: string }[] = [
  { docType: 'sale_deed', label: 'Sale Deed' },
  { docType: 'noc', label: 'NOC' },
  { docType: 'encumbrance_certificate', label: 'Encumbrance Certificate' },
  { docType: 'property_tax_receipt', label: 'Property Tax Receipt' },
];

const PropertyDocRow: React.FC<{
  docType: string;
  label: string;
  sessionId: string;
  token: string;
  uploadedFileName?: string;
  onUploaded: (docType: string, fileName: string, data: any) => void;
}> = ({ docType, label, sessionId, token, uploadedFileName, onUploaded }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>(uploadedFileName ? 'done' : 'idle');
  const [fileName, setFileName] = useState<string>(uploadedFileName ?? '');

  const handleFile = async (file: File) => {
    setFileName(file.name);
    setStatus('uploading');
    try {
      const data = await uploadPropertyDocument(file, docType, sessionId, token);
      setStatus('done');
      onUploaded(docType, file.name, data);
    } catch {
      setStatus('error');
    }
  };

  return (
    <div
      onClick={() => status !== 'uploading' && inputRef.current?.click()}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        border: `1.5px solid ${status === 'done' ? '#00b894' : status === 'error' ? '#ef4444' : '#d1d5db'}`,
        borderRadius: 12, padding: '12px 14px', cursor: 'pointer',
        background: status === 'done' ? '#f0fdf4' : '#fafafa', transition: 'all .2s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        hidden
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <div style={{ minWidth: 0, flex: 1 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#1e3a6e' }}>{label}</p>
        {status === 'idle' && <p style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>PDF, JPG or PNG</p>}
        {status === 'uploading' && <p style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>Uploading {fileName}…</p>}
        {status === 'done' && <p style={{ fontSize: 11, color: '#00b894', fontWeight: 600, marginTop: 2 }}>{fileName}</p>}
        {status === 'error' && <p style={{ fontSize: 11, color: '#ef4444', marginTop: 2 }}>Upload failed. Try again.</p>}
      </div>
      {status === 'done' ? (
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#00b894" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
      ) : (
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#9ca3af" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
      )}
    </div>
  );
};

const PropertyDocumentChecklist: React.FC<{
  sessionId: string;
  token: string;
  onResult?: (data: any) => void;
}> = ({ sessionId, token, onResult }) => {
  const [existing, setExisting] = useState<Record<string, string>>({});

  useEffect(() => {
    getPropertyDocuments(sessionId, token)
      .then((docs: any) => {
        const map: Record<string, string> = {};
        (docs || []).forEach((d: any) => { map[d.doc_type] = d.file_name; });
        setExisting(map);
      })
      .catch(() => {});
  }, [sessionId, token]);

  const handleUploaded = (docType: string, fileName: string, data: any) => {
    setExisting(prev => ({ ...prev, [docType]: fileName }));
    onResult?.(data);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {PROPERTY_DOC_TYPES.map(d => (
        <PropertyDocRow
          key={d.docType}
          docType={d.docType}
          label={d.label}
          sessionId={sessionId}
          token={token}
          uploadedFileName={existing[d.docType]}
          onUploaded={handleUploaded}
        />
      ))}
    </div>
  );
};

const KycFileUploader: React.FC<{
  label: string;
  docType: string;
  token: string;
  onUploaded?: (url: string) => void;
  onResult?: (data: any) => void;
  multiple?: boolean;
}> = ({ label, docType, token, onUploaded, onResult, multiple }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle');
  const [fileNames, setFileNames] = useState<string[]>([]);

  const handleFile = async (file: File) => {
    setFileNames(prev => (multiple ? [...prev, file.name] : [file.name]));
    setStatus('uploading');
    try {
      const data: any = await uploadDocument(file, docType, token); // 🔌 BACKEND: POST /kyc/upload
      setStatus('done');
      onUploaded?.(data.url);
      onResult?.(data);
    } catch {
      setStatus('error');
    }
  };

  const handleFiles = (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!multiple) {
      if (list[0]) handleFile(list[0]);
      return;
    }
    list.forEach(handleFile);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  };

  const fileName = fileNames[fileNames.length - 1] ?? '';

  return (
    <div
      onDragOver={e => e.preventDefault()}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${status === 'done' ? '#00b894' : status === 'error' ? '#ef4444' : '#d1d5db'}`,
        borderRadius: 12, padding: '20px 16px', textAlign: 'center', cursor: 'pointer',
        background: status === 'done' ? '#f0fdf4' : '#fafafa', transition: 'all .2s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        hidden
        multiple={multiple}
        onChange={e => e.target.files?.length && handleFiles(e.target.files)}
      />
      {status === 'idle' && (
        <>
          <svg style={{ margin:'0 auto 8px' }} width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="#9ca3af" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <p style={{ fontSize: 13, color: '#6b7280' }}><strong style={{ color: '#1e3a6e' }}>Click to upload</strong> or drag &amp; drop</p>
          <p style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>{label}</p>
        </>
      )}
      {status === 'uploading' && <p style={{ fontSize: 13, color: '#1e3a6e' }}>Uploading {fileName}…</p>}
      {status === 'done' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#00b894" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
          <p style={{ fontSize: 13, color: '#00b894', fontWeight: 600 }}>
            {multiple && fileNames.length > 1 ? `${fileNames.length} files uploaded` : `${fileName} uploaded`}
          </p>
        </div>
      )}
      {status === 'error' && <p style={{ fontSize: 13, color: '#ef4444' }}>Upload failed. Try again.</p>}
    </div>
  );
};

export const FileUploader: React.FC<FileUploaderProps> = ({ label, docType, token, onUploaded, onResult, multiple, mode = 'kyc', sessionId }) => {
  if (mode === 'property') {
    if (!sessionId) return null;
    return <PropertyDocumentChecklist sessionId={sessionId} token={token} onResult={onResult} />;
  }
  return <KycFileUploader label={label} docType={docType} token={token} onUploaded={onUploaded} onResult={onResult} multiple={multiple} />;
};
