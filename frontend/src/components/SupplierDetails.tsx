import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Container,
  Grid,
  Typography,
  Tabs,
  Tab,
  Paper,
  CircularProgress,
  Alert
} from '@mui/material';
import SupplierScorecard from './SupplierScorecard';
import EPCISSubmissionForm from './EPCISSubmissionForm';
import ValidationErrorsList from './ValidationErrorsList';
import api from '../services/api';
import { Supplier, EPCISSubmission } from '../types/supplier';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`supplier-tabpanel-${index}`}
      aria-labelledby={`supplier-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `supplier-tab-${index}`,
    'aria-controls': `supplier-tabpanel-${index}`,
  };
}

const SupplierDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [submission, setSubmission] = useState<EPCISSubmission | null>(null);
  const [refreshSubmission, setRefreshSubmission] = useState<boolean>(false);

  useEffect(() => {
    const fetchSupplier = async () => {
      try {
        setLoading(true);
        const data = await api.getSupplier(id!);
        setSupplier(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching supplier details:', err);
        setError('Failed to load supplier details');
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchSupplier();
    }
  }, [id]);

  useEffect(() => {
    const fetchSubmission = async () => {
      if (!submission?.id) return;
      
      try {
        const data = await api.getSubmissionDetails(submission.id);
        setSubmission(data);
      } catch (err) {
        console.error('Error refreshing submission:', err);
      }
    };

    if (refreshSubmission && submission) {
      fetchSubmission();
      setRefreshSubmission(false);
    }
  }, [refreshSubmission, submission]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleSubmissionComplete = async (submissionId: string, success: boolean) => {
    if (success) {
      try {
        const submissionData = await api.getSubmissionDetails(submissionId);
        setSubmission(submissionData);
        if (submissionData.error_count > 0 || submissionData.warning_count > 0) {
          // Switch to validation tab if there are errors
          setTabValue(2);
        }
      } catch (err) {
        console.error('Error fetching submission details:', err);
      }
    }
  };

  const handleErrorResolved = () => {
    setRefreshSubmission(true);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !supplier) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">
          {error || 'Supplier not found'}
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        {supplier.name}
      </Typography>

      <Paper sx={{ width: '100%' }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          variant="fullWidth"
        >
          <Tab label="Scorecard" {...a11yProps(0)} />
          <Tab label="Upload EPCIS" {...a11yProps(1)} />
          <Tab label="Validation" {...a11yProps(2)} />
        </Tabs>
        
        <TabPanel value={tabValue} index={0}>
          <SupplierScorecard supplierId={id!} />
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          <EPCISSubmissionForm 
            supplierId={id!} 
            onSubmissionComplete={handleSubmissionComplete} 
          />
          
          <Box mt={4}>
            <Typography variant="h6" gutterBottom>
              Recent Submissions
            </Typography>
            {/* TODO: Add recent submissions list component here */}
          </Box>
        </TabPanel>
        
        <TabPanel value={tabValue} index={2}>
          {submission ? (
            <ValidationErrorsList 
              errors={submission.errors} 
              submissionId={submission.id} 
              onErrorResolved={handleErrorResolved}
            />
          ) : (
            <Alert severity="info">
              Upload an EPCIS file to see validation results or select a previous submission.
            </Alert>
          )}
        </TabPanel>
      </Paper>
    </Container>
  );
};

export default SupplierDetails;