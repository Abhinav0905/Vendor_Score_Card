import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Stack,
  Collapse,
  IconButton
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import FilePreviewPanel from './FilePreviewPanel';
import CloseIcon from '@mui/icons-material/Close';
import VisibilityIcon from '@mui/icons-material/Visibility';
import axios from 'axios';
import api from '../services/api';

interface SubmissionResult {
  id: string;
  submission_id?: string; // Add for backward compatibility
  file_name: string;
  status: string;
  error_count: number;
  warning_count: number;
  errors?: any[];
  message?: string;
  success?: boolean;
}

interface EPCISFileDropZoneProps {
  onFileUploaded?: (submissionId: string, fileName: string) => void;
}

const EPCISFileDropZone: React.FC<EPCISFileDropZoneProps> = ({ onFileUploaded }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmission, setLastSubmission] = useState<SubmissionResult | null>(null);
  const [showPreview, setShowPreview] = useState(false);

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

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await axios.post('http://localhost:8000/epcis/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (err: any) {
      console.error('File upload error:', err);
      
      if (err.response?.status === 409 && err.response?.data?.submission_id) {
        return {
          success: false,
          isDuplicate: true,
          message: 'Duplicate file detected',
          submissionId: err.response.data.submission_id
        };
      }
      
      return {
        success: false,
        message: err.response?.data?.message || err.message || 'An error occurred during upload'
      };
    }
  };

  const processFileUpload = async (file: File) => {
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    
    if (fileExt !== 'xml' && fileExt !== 'json') {
      setError('Only XML and JSON files are supported');
      return;
    }
    
    setLoading(true);
    setError(null);
    setShowPreview(false);
    
    const result = await uploadFile(file);
    
    if (result.success && result.data) {
      const submissionData = result.data;
      
      // Use the correct submission ID - it could be in different fields depending on the response
      const submissionId = submissionData.submission_id || submissionData.id;
      
      if (!submissionId) {
        console.error('No submission ID in response:', submissionData);
        setError('Server did not return a valid submission ID');
        setLoading(false);
        return;
      }

      // Update submission data with the correct ID
      const submission: SubmissionResult = {
        ...submissionData,
        id: submissionId
      };

      setLastSubmission(submission);
      setShowPreview(true);
      console.log("File upload successful, submission:", submission);
      
      if (onFileUploaded) {
        onFileUploaded(submissionId, submission.file_name);
      }

      // If the submission has validation results
      if (submission.error_count > 0 || submission.warning_count > 0) {
        try {
          const validationResponse = await axios.get(`http://localhost:8000/epcis/submissions/${submissionId}/validation`);
          if (validationResponse.data?.errors) {
            setLastSubmission(prev => ({
              ...prev!,
              errors: validationResponse.data.errors
            }));
          }
        } catch (validationError) {
          console.error('Error fetching validation results:', validationError);
        }
      }
    } else {
      setError(result.message || 'Failed to upload file');
      
      if (result.isDuplicate && result.submissionId) {
        try {
          const submissionResponse = await axios.get(`http://localhost:8000/epcis/submissions/${result.submissionId}`);
          if (submissionResponse.data?.submission) {
            setLastSubmission(submissionResponse.data.submission);
            setShowPreview(true);
            
            if (onFileUploaded) {
              onFileUploaded(result.submissionId, submissionResponse.data.submission.file_name);
            }
          }
        } catch (fetchErr) {
          console.error('Error fetching existing submission:', fetchErr);
        }
      }
    }
    
    setLoading(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;
    
    await processFileUpload(files[0]);
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    await processFileUpload(file);
    
    // Clear the file input value to allow uploading the same file again
    e.target.value = '';
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>
        EPCIS File Upload
      </Typography>
      
      {error && (
        <Alert 
          severity="error"
          action={
            <IconButton
              size="small"
              onClick={() => setError(null)}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          }
        >
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
            <input
              type="file"
              accept=".xml,.json"
              id="epcis-file-input"
              onChange={handleFileInputChange}
              style={{ display: 'none' }}
            />
            <CloudUploadIcon sx={{ fontSize: 48, color: 'action.active', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Drop EPCIS File Here
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              Supported formats: XML, JSON
            </Typography>
            <Button
              component="label"
              htmlFor="epcis-file-input"
              variant="contained"
              sx={{ mt: 2 }}
            >
              Browse Files
            </Button>
          </>
        )}
      </Paper>

      {lastSubmission && !loading && (
        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle1">
              File Information
            </Typography>
            <IconButton size="small" onClick={() => setShowPreview(!showPreview)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Box>
          
          <Typography variant="body2">
            File: {lastSubmission.file_name}
          </Typography>
          
          <Typography variant="body2">
            Status: {lastSubmission.status}
          </Typography>
          
          <Stack direction="row" spacing={2} mt={1}>
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
            {lastSubmission.error_count === 0 && lastSubmission.warning_count === 0 && (
              <Typography variant="body2" color="success.main">
                No errors found, file processing completed.
              </Typography>
            )}
          </Stack>
        </Paper>
      )}
      
      <Collapse in={showPreview && !!lastSubmission}>
        {lastSubmission && (
          <FilePreviewPanel 
            submissionId={lastSubmission.id} 
            fileName={lastSubmission.file_name}
          />
        )}
      </Collapse>
    </Box>
  );
};

export default EPCISFileDropZone;