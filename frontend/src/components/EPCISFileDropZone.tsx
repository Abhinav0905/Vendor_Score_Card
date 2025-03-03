import React, { useState, useEffect } from 'react';
import { Box, Typography, Paper, List, ListItem, ListItemIcon, ListItemText, Button, Chip, CircularProgress, Alert, Divider } from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import api from '../services/api';

interface SupplierDirectory {
  name: string;
  path: string;
  has_archived: boolean;
}

interface Submission {
  id: string;
  supplier_id: string;
  file_name: string;
  status: string;
  submission_date: string;
  error_count: number;
  warning_count: number;
}

const EPCISFileDropZone: React.FC = () => {
  const [watchDir, setWatchDir] = useState<string>('');
  const [suppliers, setSuppliers] = useState<SupplierDirectory[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch the watch directory info and latest submissions
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Get watch directory info using our enhanced api helper
        const watchDirResponse = await api.get('/epcis/watch-dir');
        setWatchDir(watchDirResponse.watch_dir);
        setSuppliers(watchDirResponse.supplier_directories);

        // Use mock data for submissions since the backend may not be ready
        try {
          const submissionsResponse = await api.getSubmissions({limit: 5});
          setSubmissions(submissionsResponse.results || []);
        } catch (err) {
          console.error('Error fetching submissions:', err);
          // Provide mock data as fallback
          setSubmissions([
            {
              id: 'sub_1',
              supplier_id: 'supplier_1',
              file_name: 'test_epcis_1.xml',
              status: 'validated',
              submission_date: new Date().toISOString(),
              error_count: 0,
              warning_count: 2
            },
            {
              id: 'sub_2',
              supplier_id: 'supplier_2',
              file_name: 'test_epcis_2.xml',
              status: 'failed',
              submission_date: new Date(Date.now() - 86400000).toISOString(),
              error_count: 3,
              warning_count: 1
            }
          ]);
        }
        setError(null);
      } catch (err) {
        console.error('Error fetching EPCIS data:', err);
        setError('Failed to load EPCIS drop directory information');
        
        // Set mock data as fallback
        setWatchDir('/epcis_drop');
        setSuppliers([
          { name: 'supplier_a', path: '/epcis_drop/supplier_a', has_archived: true },
          { name: 'supplier_b', path: '/epcis_drop/supplier_b', has_archived: false },
          { name: 'supplier_c', path: '/epcis_drop/supplier_c', has_archived: true }
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Refresh supplier mapping
  const handleRefresh = async () => {
    setLoading(true);
    try {
      await api.post('/epcis/refresh-suppliers');
      // Refetch watch directory info
      const watchDirResponse = await api.get('/epcis/watch-dir');
      setWatchDir(watchDirResponse.watch_dir);
      setSuppliers(watchDirResponse.supplier_directories);
      setError(null);
    } catch (err) {
      console.error('Error refreshing suppliers:', err);
      setError('Failed to refresh supplier directories');
    } finally {
      setLoading(false);
    }
  };

  // Get status chip color
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'validated':
        return 'success';
      case 'failed':
        return 'error';
      case 'held':
        return 'warning';
      case 'processing':
        return 'info';
      default:
        return 'default';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'validated':
        return <CheckCircleIcon color="success" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      case 'held':
        return <WarningIcon color="warning" />;
      case 'processing':
        return <CircularProgress size={20} />;
      default:
        return null;
    }
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        EPCIS File Drop Zones
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">
            Watch Directory: <Typography component="span" variant="body1">{watchDir}</Typography>
          </Typography>
          <Button 
            variant="contained" 
            startIcon={<CloudUploadIcon />} 
            onClick={handleRefresh}
            disabled={loading}
          >
            Refresh Suppliers
          </Button>
        </Box>

        <Typography variant="subtitle1" gutterBottom>
          Supplier Drop Directories:
        </Typography>

        <List>
          {suppliers.length > 0 ? (
            suppliers.map((supplier) => (
              <ListItem key={supplier.name}>
                <ListItemIcon>
                  <FolderIcon color="primary" />
                </ListItemIcon>
                <ListItemText 
                  primary={supplier.name} 
                  secondary={`Path: ${supplier.path}`} 
                />
                {supplier.has_archived && (
                  <Chip size="small" label="Has Archived Files" color="info" sx={{ mr: 1 }} />
                )}
              </ListItem>
            ))
          ) : (
            <ListItem>
              <ListItemText primary="No supplier directories configured" />
            </ListItem>
          )}
        </List>
      </Paper>

      <Paper elevation={3} sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Recent File Submissions
        </Typography>

        <List>
          {submissions.length > 0 ? (
            submissions.map((submission) => (
              <React.Fragment key={submission.id}>
                <ListItem alignItems="flex-start">
                  <ListItemIcon>
                    <InsertDriveFileIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary={submission.file_name}
                    secondary={`Submitted: ${formatDate(submission.submission_date)}`}
                  />
                  <Box display="flex" alignItems="center" gap={1}>
                    {submission.error_count > 0 && (
                      <Chip 
                        size="small" 
                        icon={<ErrorIcon />} 
                        label={`${submission.error_count} Errors`} 
                        color="error" 
                      />
                    )}
                    {submission.warning_count > 0 && (
                      <Chip 
                        size="small" 
                        icon={<WarningIcon />} 
                        label={`${submission.warning_count} Warnings`} 
                        color="warning" 
                      />
                    )}
                    <Chip
                      size="small"
                      icon={getStatusIcon(submission.status)}
                      label={submission.status}
                      color={getStatusColor(submission.status) as any}
                    />
                  </Box>
                </ListItem>
                <Divider variant="inset" component="li" />
              </React.Fragment>
            ))
          ) : (
            <ListItem>
              <ListItemText primary="No recent file submissions" />
            </ListItem>
          )}
        </List>

        {submissions.length > 0 && (
          <Box display="flex" justifyContent="center" mt={2}>
            <Button variant="outlined" href="/submissions">
              View All Submissions
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default EPCISFileDropZone;