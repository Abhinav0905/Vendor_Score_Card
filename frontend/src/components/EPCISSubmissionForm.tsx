import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  FormControl, 
  InputLabel, 
  MenuItem, 
  Select, 
  Paper, 
  Alert, 
  CircularProgress, 
  Stepper, 
  Step, 
  StepLabel 
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import api from '../services/api';

interface Supplier {
  id: string;
  name: string;
}

const steps = ['Select Supplier', 'Upload File', 'Process'];

const EPCISSubmissionForm: React.FC = () => {
  // Form state
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [activeStep, setActiveStep] = useState<number>(0);
  
  // Data state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [submissionResult, setSubmissionResult] = useState<any>(null);
  
  // Fetch suppliers on component mount
  useEffect(() => {
    const fetchSuppliers = async () => {
      setLoading(true);
      try {
        // In production, replace with actual API call
        // const response = await api.get('/suppliers');
        // setSuppliers(response.data);
        
        // Mock data for now
        setSuppliers([
          { id: 'supplier_1', name: 'Supplier A' },
          { id: 'supplier_2', name: 'Supplier B' },
          { id: 'supplier_3', name: 'Supplier C' },
        ]);
        
        setError(null);
      } catch (err) {
        console.error('Error fetching suppliers:', err);
        setError('Failed to load suppliers');
      } finally {
        setLoading(false);
      }
    };
    
    fetchSuppliers();
  }, []);
  
  // File input change handler
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const selectedFile = event.target.files[0];
      
      // Check if file is XML or JSON
      const fileExt = selectedFile.name.split('.').pop()?.toLowerCase();
      if (fileExt !== 'xml' && fileExt !== 'json') {
        setError('Only XML and JSON files are supported');
        return;
      }
      
      setFile(selectedFile);
      setError(null);
      nextStep();
    }
  };
  
  // Supplier select change handler
  const handleSupplierChange = (event: React.ChangeEvent<{ value: unknown }>) => {
    setSelectedSupplierId(event.target.value as string);
    setError(null);
    nextStep();
  };
  
  // Step navigation
  const nextStep = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };
  
  const prevStep = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const resetForm = () => {
    setSelectedSupplierId('');
    setFile(null);
    setActiveStep(0);
    setSuccess(false);
    setSubmissionResult(null);
    setError(null);
  };
  
  // Form submission handler
  const handleSubmit = async () => {
    if (!file || !selectedSupplierId) {
      setError('Please select both a supplier and a file');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Create form data
      const formData = new FormData();
      formData.append('file', file);
      formData.append('supplier_id', selectedSupplierId);
      
      // Send to API
      const response = await api.post('/epcis/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      setSubmissionResult(response.data);
      setSuccess(true);
      nextStep();
    } catch (err: any) {
      console.error('Error submitting EPCIS file:', err);
      setError(err.response?.data?.message || 'Failed to submit EPCIS file');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Upload EPCIS File
      </Typography>
      
      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert severity="success" icon={<CheckCircleIcon />} sx={{ mb: 2 }}>
          File uploaded successfully!
          {submissionResult?.submission_id && (
            <Typography variant="body2">
              Submission ID: {submissionResult.submission_id}
            </Typography>
          )}
        </Alert>
      )}
      
      <Paper elevation={3} sx={{ p: 3 }}>
        {activeStep === 0 && (
          <FormControl fullWidth>
            <InputLabel id="supplier-select-label">Select Supplier</InputLabel>
            <Select
              labelId="supplier-select-label"
              value={selectedSupplierId}
              label="Select Supplier"
              onChange={handleSupplierChange}
              disabled={loading}
            >
              {suppliers.map((supplier) => (
                <MenuItem key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        
        {activeStep === 1 && (
          <Box 
            sx={{ 
              border: '2px dashed #ccc',
              borderRadius: 2,
              p: 3,
              textAlign: 'center',
              bgcolor: 'background.default',
            }}
          >
            <input
              type="file"
              id="epcis-file"
              accept=".xml,.json"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            
            <label htmlFor="epcis-file">
              <Button
                component="span"
                variant="contained"
                startIcon={<CloudUploadIcon />}
                disabled={loading}
              >
                Select EPCIS File
              </Button>
            </label>
            
            {file && (
              <Typography variant="body1" sx={{ mt: 2 }}>
                Selected file: {file.name} ({(file.size / 1024).toFixed(2)} KB)
              </Typography>
            )}
            
            <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
              Supported formats: XML, JSON
            </Typography>
          </Box>
        )}
        
        {activeStep === 2 && (
          <Box sx={{ textAlign: 'center' }}>
            {loading ? (
              <CircularProgress />
            ) : success ? (
              <Box>
                <CheckCircleIcon color="success" sx={{ fontSize: 64, mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  File Processed Successfully
                </Typography>
                
                {submissionResult && (
                  <Box sx={{ mt: 2, textAlign: 'left' }}>
                    <Typography variant="body2">
                      Status: {submissionResult.status}
                    </Typography>
                    <Typography variant="body2">
                      Errors: {submissionResult.error_count || 0}
                    </Typography>
                    <Typography variant="body2">
                      Warnings: {submissionResult.warning_count || 0}
                    </Typography>
                  </Box>
                )}
                
                <Button 
                  variant="contained" 
                  onClick={resetForm} 
                  sx={{ mt: 2 }}
                >
                  Upload Another File
                </Button>
              </Box>
            ) : (
              <Box>
                <Typography variant="h6" gutterBottom>
                  Confirm Upload
                </Typography>
                <Typography variant="body2" gutterBottom>
                  Supplier: {suppliers.find(s => s.id === selectedSupplierId)?.name}
                </Typography>
                <Typography variant="body2" gutterBottom>
                  File: {file?.name} ({file && (file.size / 1024).toFixed(2)} KB)
                </Typography>
                
                <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-between' }}>
                  <Button onClick={prevStep}>
                    Back
                  </Button>
                  <Button 
                    variant="contained" 
                    onClick={handleSubmit} 
                    disabled={loading}
                  >
                    Upload File
                  </Button>
                </Box>
              </Box>
            )}
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default EPCISSubmissionForm;