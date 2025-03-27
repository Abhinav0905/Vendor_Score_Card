import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Grid,
  Typography,
  Paper,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  TextField,
  InputAdornment,
  useTheme,
  useMediaQuery,
  Tabs,
  Tab
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import api from '../services/api';
import { DashboardStats } from '../types/supplier';
import QueryInput from './nlp/QueryInput';
import EPCISFileDropZone from './EPCISFileDropZone';
import FilePreviewPanel from './FilePreviewPanel';
import PerformanceChart from './charts/PerformanceChart';

// Register Chart.js components
ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

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
      id={`dashboard-tabpanel-${index}`}
      aria-labelledby={`dashboard-tab-${index}`}
      {...other}
      style={{ height: '100%' }}
    >
      {value === index && (
        <Box sx={{ height: '100%', pt: 2 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [nlpQueryResult, setNlpQueryResult] = useState<any>(null);
  const [tabValue, setTabValue] = useState<number>(0);
  // New state for tracking uploaded files
  const [activeFileSubmissionId, setActiveFileSubmissionId] = useState<string | null>(null);
  const [activeFileName, setActiveFileName] = useState<string | null>(null);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // This function will be passed to EPCISFileDropZone to notify Dashboard when a file is uploaded
  const handleFileUploaded = (submissionId: string, fileName: string) => {
    console.log("Dashboard received file upload notification:", submissionId, fileName);
    setActiveFileSubmissionId(submissionId);
    setActiveFileName(fileName);
  };

  const fetchDashboardStats = useCallback(async () => {
    try {
      const data = await api.getDashboardStats();
      setStats(data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching dashboard stats:', err);
      setError(err?.response?.data?.detail || err.message || 'Failed to load dashboard statistics');
    } finally {
      // Always set loading to false regardless of success or error
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    fetchDashboardStats();

    // Set up polling with a longer interval (30 seconds instead of frequent polling)
    const interval = setInterval(fetchDashboardStats, 30000);

    return () => clearInterval(interval);
  }, []);

  // Add debounce to validation results fetching
  useEffect(() => {
    if (activeFileSubmissionId) {
      const timer = setTimeout(() => {
        fetchValidationResults(activeFileSubmissionId);
      }, 2000); // Wait 2 seconds before fetching validation results

      return () => clearTimeout(timer);
    }
  }, [activeFileSubmissionId]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleNlpQueryComplete = (result: any) => {
    setNlpQueryResult(result);
  };

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !stats) {
    return (
      <Box p={3}>
        <Alert severity="error">{error || 'Failed to load dashboard'}</Alert>
      </Box>
    );
  }

  // Dashboard data transformations
  const statusDistributionData = {
    labels: Object.keys(stats.submission_by_status),
    datasets: [{
      data: Object.values(stats.submission_by_status),
      backgroundColor: ['#4caf50', '#ff9800', '#f44336', '#2196f3'],
    }]
  };

  // Create supplier submissions stacked bar chart with real data from API
  const supplierSubmissionsData = {
    labels: stats.top_suppliers.map(supplier => supplier.name),
    datasets: [
      {
        label: 'Successful Submissions',
        data: stats.top_suppliers.map(supplier => supplier.success_count),
        backgroundColor: '#4caf50', // Green for successful submissions
      },
      {
        label: 'Failed Submissions',
        data: stats.top_suppliers.map(supplier => supplier.failure_count),
        backgroundColor: '#f44336', // Red for failed submissions
      }
    ]
  };

  // Create supplier error rate chart with real data from API
  const supplierErrorRateData = {
    labels: stats.top_suppliers.map(supplier => supplier.name),
    datasets: [
      {
        label: 'Error Rate (%)',
        data: stats.top_suppliers.map(supplier => supplier.error_rate),
        backgroundColor: '#ff9800', // Orange for error rates
        barPercentage: 0.6,
        borderRadius: 4,
      }
    ]
  };

  // Add console log to help debug the discrepancy
  console.log('Dashboard Stats:', {
    total: stats.total_submissions,
    successful: stats.successful_submissions,
    failed: stats.failed_submissions,
    sum: stats.successful_submissions + stats.failed_submissions,
    byStatus: stats.submission_by_status,
    suppliers: stats.top_suppliers
  });

  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100vh', 
      overflow: 'hidden' 
    }}>
      {/* Header Section */}
      <Box sx={{ 
        borderBottom: 1, 
        borderColor: 'divider', 
        p: 2, 
        bgcolor: 'background.paper' 
      }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h5" component="h1">
            EPCIS Dashboard
          </Typography>
          
          <TextField
            placeholder="Search..."
            size="small"
            variant="outlined"
            value={searchQuery}
            onChange={handleSearchChange}
            sx={{ width: '250px' }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
        </Box>
      </Box>

      {/* Main Content Area with Tabs */}
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        flexGrow: 1,
        overflow: 'hidden'
      }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange}
            aria-label="dashboard tabs"
            variant={isMobile ? "scrollable" : "fullWidth"}
          >
            <Tab label="File Upload & Validation" />
            <Tab label="Dashboard Analytics" />
          </Tabs>
        </Box>

        <Box sx={{ 
          flexGrow: 1, 
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* File Upload & Validation Tab */}
          <TabPanel value={tabValue} index={0}>
            <Box sx={{ 
              display: 'flex', 
              flexDirection: isMobile ? 'column' : 'row', 
              height: '100%' 
            }}>
              {/* Left Sidebar - File Drop Zone */}
              <Box
                sx={{
                  width: isMobile ? '100%' : '30%',
                  height: isMobile ? 'auto' : '100%',
                  flexShrink: 0,
                  bgcolor: 'background.paper',
                  borderRight: isMobile ? 0 : 1,
                  borderBottom: isMobile ? 1 : 0,
                  borderColor: 'divider',
                  p: 2,
                  overflow: 'auto'
                }}
              >
                <EPCISFileDropZone onFileUploaded={handleFileUploaded} />
              </Box>

              {/* Main Content - Expanded area for file preview and errors */}
              <Box sx={{ 
                flexGrow: 1, 
                p: 3, 
                overflow: 'auto',
                display: isMobile ? 'block' : 'flex',
                flexDirection: 'column',
                height: '100%' 
              }}>
                <Typography variant="h6" gutterBottom>
                  File Validation
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Upload an EPCIS file using the drop zone on the left. Files will be validated, and any errors will be displayed here.
                </Typography>

                {/* Show file validation results if a file has been uploaded */}
                {activeFileSubmissionId ? (
                  <Box sx={{
                    bgcolor: 'background.paper',
                    height: 'calc(100% - 80px)', // Adjust for the header
                    borderRadius: 1,
                    overflow: 'auto'
                  }}>
                    {/* Direct use of FilePreviewPanel component */}
                    <FilePreviewPanel 
                      submissionId={activeFileSubmissionId} 
                      fileName={activeFileName || 'EPCIS File'} 
                    />
                  </Box>
                ) : (
                  <Box sx={{ 
                    bgcolor: 'background.default', 
                    p: 2, 
                    borderRadius: 1,
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <Typography color="text.secondary">
                      Upload a file to see the validation results.
                    </Typography>
                  </Box>
                )}
              </Box>
            </Box>
          </TabPanel>

          {/* Dashboard Analytics Tab */}
          <TabPanel value={tabValue} index={1}>
            <Box sx={{ p: 2, overflow: 'auto' }}>
              {/* NLP Query Input */}
              <Box mb={4}>
                <QueryInput onQueryComplete={handleNlpQueryComplete} />
              </Box>

              {/* Summary Cards */}
              <Grid container spacing={3} mb={4}>
                <Grid item xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>Total Submissions</Typography>
                      <Typography variant="h3" color="primary">
                        {stats.total_submissions}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                
                <Grid item xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>Success Rate</Typography>
                      <Typography variant="h3" color="success.main">
                        {((stats.successful_submissions / stats.total_submissions) * 100).toFixed(1)}%
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                
                <Grid item xs={12} md={4}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>Failed Submissions</Typography>
                      <Typography variant="h3" color="error">
                        {stats.failed_submissions}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              {/* Charts */}
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="h6" gutterBottom>Error Rates by Company</Typography>
                    <Box height={300}>
                      <Bar 
                        data={supplierErrorRateData}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          indexAxis: 'y' as const,
                          plugins: {
                            legend: {
                              display: false,
                            },
                            tooltip: {
                              callbacks: {
                                label: function(context) {
                                  return `Error rate: ${context.raw}%`;
                                }
                              }
                            }
                          },
                          scales: {
                            x: {
                              beginAtZero: true,
                              max: 100,
                              title: {
                                display: true,
                                text: 'Error Rate (%)'
                              },
                              ticks: {
                                callback: function(value) {
                                  return value + '%';
                                }
                              }
                            },
                            y: {
                              title: {
                                display: true,
                                text: 'Companies'
                              }
                            }
                          }
                        }}
                      />
                    </Box>
                  </Paper>
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="h6" gutterBottom>Submissions by Company</Typography>
                    <Box height={300}>
                      <Bar 
                        data={supplierSubmissionsData} 
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: {
                              position: 'top',
                            },
                            tooltip: {
                              callbacks: {
                                label: function(context) {
                                  const label = context.dataset.label || '';
                                  const value = context.raw || 0;
                                  return `${label}: ${value}`;
                                },
                                footer: function(tooltipItems) {
                                  const total = tooltipItems.reduce((sum, item) => sum + (item.raw as number), 0);
                                  return `Total: ${total} submissions`;
                                }
                              }
                            }
                          },
                          scales: {
                            x: {
                              stacked: true,
                              title: {
                                display: true,
                                text: 'Companies'
                              }
                            },
                            y: {
                              stacked: true,
                              title: {
                                display: true,
                                text: 'Number of Submissions'
                              }
                            }
                          }
                        }}
                      />
                    </Box>
                  </Paper>
                </Grid>
              </Grid>
            </Box>
          </TabPanel>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;

function fetchValidationResults(activeFileSubmissionId: string) {
  console.log("Fetching validation results for submission:", activeFileSubmissionId);
  // TODO: Implement actual validation results fetching
  // This is a placeholder that doesn't throw an error
  return Promise.resolve({
    status: "pending",
    errors: []
  });
}
