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
  useMediaQuery
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

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [nlpQueryResult, setNlpQueryResult] = useState<any>(null);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const fetchDashboardStats = useCallback(async () => {
    try {
      const data = await api.getDashboardStats();
      setStats(data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching dashboard stats:', err);
      setError(err?.response?.data?.detail || err.message || 'Failed to load dashboard statistics');
    }
  }, []);

  useEffect(() => {
    const initialLoad = async () => {
      setLoading(true);
      await fetchDashboardStats();
      setLoading(false);
    };
    
    initialLoad();

    // Set up polling every 5 seconds
    const intervalId = setInterval(fetchDashboardStats, 5000);

    // Cleanup interval on component unmount
    return () => clearInterval(intervalId);
  }, [fetchDashboardStats]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleNlpQueryComplete = (result: any) => {
    setNlpQueryResult(result);
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

  const errorTypeData = {
    labels: Object.keys(stats.error_type_distribution),
    datasets: [{
      data: Object.values(stats.error_type_distribution),
      backgroundColor: theme.palette.primary.main,
    }]
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row' }}>
      {/* Left Sidebar - File Drop Zone */}
      <Box
        sx={{
          width: isMobile ? '100%' : '300px',
          flexShrink: 0,
          bgcolor: 'background.paper',
          borderRight: isMobile ? 0 : 1,
          borderBottom: isMobile ? 1 : 0,
          borderColor: 'divider',
          p: 2
        }}
      >
        <EPCISFileDropZone />
      </Box>

      {/* Main Content */}
      <Box sx={{ flexGrow: 1, p: 3, overflow: 'auto' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h4" component="h1">
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
              <Typography variant="h6" gutterBottom>Submission Status Distribution</Typography>
              <Box height={300}>
                <Doughnut 
                  data={statusDistributionData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        position: 'right',
                      },
                    },
                  }}
                />
              </Box>
            </Paper>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>Error Type Distribution</Typography>
              <Box height={300}>
                <Bar 
                  data={errorTypeData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        display: false,
                      },
                    },
                  }}
                />
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
};

export default Dashboard;