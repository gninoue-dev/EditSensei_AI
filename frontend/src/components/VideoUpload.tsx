import React, { useState } from 'react';
import { apiService } from '../services/api';

interface VideoUploadProps {
  onUploadSuccess?: (filename: string, filepath: string) => void;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiService.uploadVideo(file);
      onUploadSuccess?.(result.filename, result.filepath);
    } catch (err: any) {
      setError(err.message || 'Erreur upload vidéo');
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleUpload(file);
    }
  };

  return (
    <div
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      className={`border-2 border-dashed p-6 rounded-lg text-center transition ${
        dragActive
          ? 'border-primary bg-light'
          : 'border-gray-300 hover:border-primary'
      }`}
    >
      <input
        type="file"
        accept="video/*"
        onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
        className="hidden"
        id="video-input"
      />

      <label htmlFor="video-input" className="cursor-pointer">
        {loading ? (
          <div>
            <p className="text-primary font-medium">Upload en cours...</p>
          </div>
        ) : (
          <div>
            <p className="text-lg font-medium text-dark">📹 Télécharger vidéo</p>
            <p className="text-sm text-gray-600 mt-1">
              Glissez une vidéo ou cliquez pour sélectionner
            </p>
          </div>
        )}
      </label>

      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
    </div>
  );
}
