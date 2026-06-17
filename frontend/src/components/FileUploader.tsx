import React, { useRef, useState } from 'react';
import { uploadDocument } from '../services/api';

interface FileUploaderProps {
  label: string;
  docType: string;
  token: string;
  onUploaded?: (url: string) => void;
}

export const FileUploader: React.FC<FileUploaderProps> = ({ label, docType, token, onUploaded }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle');
  const [fileName, setFileName] = useState('');

  const handleFile = async (file: File) => {
    setFileName(file.name);
    setStatus('uploading');
    try {
      const data: any = await uploadDocument(file, docType, token); // 🔌 BACKEND: POST /documents/upload
      setStatus('done');
      onUploaded?.(data.url);
    } catch {
      setStatus('error');
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

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
      <input ref={inputRef} type="file" hidden onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
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
          <p style={{ fontSize: 13, color: '#00b894', fontWeight: 600 }}>{fileName} uploaded</p>
        </div>
      )}
      {status === 'error' && <p style={{ fontSize: 13, color: '#ef4444' }}>Upload failed. Try again.</p>}
    </div>
  );
};
