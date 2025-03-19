import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import api from '../services/api';

interface SubmissionResult {
  id: string;
  file_name: string;
  status: string;
  error_count: number;
  warning_count: number;
}

const EPCISFileDropZone: React.FC = () => {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmission, setLastSubmission] = useState<SubmissionResult | null>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    setError(null);

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    const file = files[0];
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    
    if (fileExt !== 'xml' && fileExt !== 'json') {
      setError('Only XML and JSON files are supported');
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post('/epcis/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      setLastSubmission(response.data);
    } catch (err: any) {
      console.error('Error uploading file:', err);
      setError(err.response?.data?.message || 'Failed to upload file');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>
        EPCIS File Upload
      </Typography>
      
      {error && (
        <Alert severity="error">
          {error}
        </Alert>
      )}

      <Paper
        sx={{
          p: 3,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          border: theme => `2px dashed ${isDragging ? theme.palette.primary.main : theme.palette.divider}`,
          bgcolor: theme => isDragging ? 'action.hover' : 'background.paper',
          transition: 'all 0.2s ease',
          cursor: 'pointer'
        }}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {loading ? (
          <CircularProgress />
        ) : (
          <>
            <CloudUploadIcon sx={{ fontSize: 48, color: 'action.active', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Drop EPCIS File Here
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Supported formats: XML, JSON
            </Typography>
          </>
        )}
      </Paper>

      {lastSubmission && !loading && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Last Upload
          </Typography>
          <Typography variant="body2">
            File: {lastSubmission.file_name}
          </Typography>
          <Typography variant="body2">
            Status: {lastSubmission.status}
          </Typography>
          {lastSubmission.error_count > 0 && (
            <Typography variant="body2" color="error">
              Errors: {lastSubmission.error_count}
            </Typography>
          )}
          {lastSubmission.warning_count > 0 && (
            <Typography variant="body2" color="warning.main">
              Warnings: {lastSubmission.warning_count}
            </Typography>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default EPCISFileDropZone;