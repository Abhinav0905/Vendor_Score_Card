import React, { useState, useEffect } from 'react';
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
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  InputAdornment
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
import { DashboardStats, TopSupplier } from '../types/supplier';
import QueryInput from './nlp/QueryInput';
import EPCISFileDropZone from './EPCISFileDropZone';
import EPCISSubmissionForm from './EPCISSubmissionForm';
import SupplierScorecard from './SupplierScorecard';
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

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        setLoading(true);
        // For now, use mock data instead of API call since backend might not be fully set up
        // const data = await api.getDashboardStats();
        const mockData: DashboardStats = {
          total_submissions: 125,
          successful_submissions: 98,
          failed_submissions: 27,
          submission_by_status: {
            validated: 98,
            held: 15,
            failed: 7,
            reprocessed: 5
          },
          top_suppliers: [
            { id: '1', name: 'Supplier A', submission_count: 42 },
            { id: '2', name: 'Supplier B', submission_count: 28 },
            { id: '3', name: 'Supplier C', submission_count: 20 }
          ],
          error_type_distribution: {
            structure: 12,
            field: 35,
            sequence: 18,
            aggregation: 7
          }
        };
        
        setStats(mockData);
        setError(null);
      } catch (err) {
        console.error('Error fetching dashboard stats:', err);
        setError('Failed to load dashboard statistics');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

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
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">
          {error || 'Failed to load dashboard data'}
        </Alert>
      </Container>
    );
  }

  // Prepare data for status distribution chart
  const statusDistributionData = {
    labels: Object.keys(stats.submission_by_status).map(
      status => status.charAt(0).toUpperCase() + status.slice(1)
    ),
    datasets: [
      {
        data: Object.values(stats.submission_by_status),
        backgroundColor: [
          'rgba(54, 162, 235, 0.6)',  // validated
          'rgba(255, 206, 86, 0.6)',  // held
          'rgba(75, 192, 192, 0.6)',  // reprocessed
          'rgba(255, 99, 132, 0.6)',  // failed
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(255, 99, 132, 1)',
        ],
        borderWidth: 1,
      },
    ],
  };

  // Prepare data for error type distribution chart
  const errorTypeLabels = Object.keys(stats.error_type_distribution);
  const errorTypeData = {
    labels: errorTypeLabels.map(type => type.charAt(0).toUpperCase() + type.slice(1)),
    datasets: [
      {
        label: 'Error Count',
        data: errorTypeLabels.map(type => stats.error_type_distribution[type]),
        backgroundColor: 'rgba(255, 99, 132, 0.6)',
        borderColor: 'rgba(255, 99, 132, 1)',
        borderWidth: 1,
      },
    ],
  };

  // Filter suppliers based on search query if needed
  const filteredSuppliers = stats.top_suppliers.filter(supplier =>
    searchQuery === '' || supplier.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 8 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Supplier Scorecard Dashboard
        </Typography>
        
        <TextField
          placeholder="Search suppliers..."
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
      {/* NLP query component */}
      <Box mb={4}>
        <QueryInput onQueryComplete={handleNlpQueryComplete} />
      </Box>
      <Grid container spacing={3}>
        {/* EPCIS File Drop Zone */}
        <Grid item xs={12}>
          <EPCISFileDropZone />
        </Grid>
        {/* EPCIS Submission Form */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <EPCISSubmissionForm />
          </Paper>
        </Grid>
        {/* Performance Overview */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Performance Overview
            </Typography>
            <PerformanceChart data={[
              { month: 'Jan', accuracy: 92, errors: 12 },
              { month: 'Feb', accuracy: 88, errors: 15 },
              { month: 'Mar', accuracy: 95, errors: 8 },
              { month: 'Apr', accuracy: 94, errors: 10 },
              { month: 'May', accuracy: 96, errors: 7 },
              { month: 'Jun', accuracy: 93, errors: 11 }
            ]} />
          </Paper>
        </Grid>
        {/* Summary cards */}
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
                {stats.total_submissions > 0 
                  ? `${((stats.successful_submissions / stats.total_submissions) * 100).toFixed(1)}%` 
                  : '0%'
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Failure Rate</Typography>
              <Typography variant="h3" color="error">
                {stats.total_submissions > 0 
                  ? `${((stats.failed_submissions / stats.total_submissions) * 100).toFixed(1)}%` 
                  : '0%'
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        {/* Charts */}
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
        
        {/* Top Suppliers */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Top Suppliers by Submission Volume
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell><strong>Supplier Name</strong></TableCell>
                    <TableCell align="right"><strong>Submissions</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredSuppliers.map((supplier: TopSupplier) => (
                    <TableRow key={supplier.id}>
                      <TableCell>
                        {supplier.name}
                      </TableCell>
                      <TableCell align="right">{supplier.submission_count}</TableCell>
                    </TableRow>
                  ))}
                  {filteredSuppliers.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={2} align="center">No suppliers found matching your search</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Dashboard;