import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Grid, 
  CircularProgress,
  Divider,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  SelectChangeEvent,
  Alert,
  useTheme
} from '@mui/material';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import api from '../services/api';
import { SupplierScorecard as ScorecardType } from '../types/supplier';
import VendorErrorAnalytics from './VendorErrorAnalytics';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface SupplierScorecardProps {
  supplierId: string;
}

const SupplierScorecard: React.FC<SupplierScorecardProps> = ({ supplierId }) => {
  const [scorecard, setScorecard] = useState<ScorecardType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [timeRange, setTimeRange] = useState<number>(30);
  const [error, setError] = useState<string | null>(null);
  const theme = useTheme();

  useEffect(() => {
    const fetchScorecard = async () => {
      try {
        setLoading(true);
        const data = await api.getSupplierScorecard(supplierId, timeRange);
        setScorecard(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching supplier scorecard:', err);
        setError('Failed to load supplier scorecard');
      } finally {
        setLoading(false);
      }
    };

    fetchScorecard();
  }, [supplierId, timeRange]);

  const handleTimeRangeChange = (event: SelectChangeEvent<number>) => {
    setTimeRange(event.target.value as number);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box textAlign="center" p={2}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  if (!scorecard) {
    return (
      <Box textAlign="center" p={2}>
        <Typography>No scorecard data available for this supplier</Typography>
      </Box>
    );
  }

  // Prepare chart data for weekly trends
  const weeklyTrendData = {
    labels: scorecard.weekly_trends.map(trend => trend.week),
    datasets: [
      {
        label: 'Error Rate (%)',
        data: scorecard.weekly_trends.map(trend => trend.error_rate),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
        yAxisID: 'y',
      },
      {
        label: 'Submissions',
        data: scorecard.weekly_trends.map(trend => trend.submissions),
        borderColor: 'rgb(53, 162, 235)',
        backgroundColor: 'rgba(53, 162, 235, 0.5)',
        yAxisID: 'y1',
      }
    ]
  };

  const weeklyOptions: ChartOptions<'line'> = {
    responsive: true,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    scales: {
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: 'Error Rate (%)'
        }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        grid: {
          drawOnChartArea: false,
        },
        title: {
          display: true,
          text: 'Submissions'
        }
      },
    },
  };

  // Prepare chart data for error types
  const errorTypeLabels = Object.keys(scorecard.error_stats.error_type_breakdown);
  const errorTypeData = {
    labels: errorTypeLabels,
    datasets: [
      {
        label: 'Errors by Type',
        data: errorTypeLabels.map(type => scorecard.error_stats.error_type_breakdown[type]),
        backgroundColor: [
          'rgba(255, 99, 132, 0.6)',
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)',
        ]
      }
    ]
  };

  // Transform weekly trends data for the error analytics component
  const errorTrends = scorecard.weekly_trends.map(trend => ({
    date: trend.week,
    errorCount: trend.errors,
    errorRate: trend.error_rate
  }));

  // Transform error types data
  const errorTypes = Object.entries(scorecard.error_stats.error_type_breakdown).map(([type, count]) => ({
    type: type.charAt(0).toUpperCase() + type.slice(1),
    count,
    severity: type.includes('warning') ? 'warning' as const : 'error' as const
  }));

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h5" component="h2">
            Supplier Scorecard: {scorecard.supplier_name}
          </Typography>
          <FormControl variant="outlined" size="small" style={{ width: 150 }}>
            <InputLabel id="time-range-label">Time Range</InputLabel>
            <Select
              labelId="time-range-label"
              value={timeRange}
              onChange={handleTimeRangeChange}
              label="Time Range"
            >
              <MenuItem value={7}>Last 7 days</MenuItem>
              <MenuItem value={30}>Last 30 days</MenuItem>
              <MenuItem value={90}>Last 90 days</MenuItem>
              <MenuItem value={180}>Last 6 months</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Typography variant="body2" color="textSecondary" gutterBottom>
          {scorecard.time_period}
        </Typography>

        <Grid container spacing={3} sx={{ mt: 1 }}>
          {/* Key metrics */}
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>Data Accuracy</Typography>
                <Box display="flex" alignItems="center">
                  <Typography variant="h4">{scorecard.data_accuracy.toFixed(1)}%</Typography>
                  <Chip 
                    label={scorecard.data_accuracy > 90 ? "Good" : scorecard.data_accuracy > 70 ? "Average" : "Poor"} 
                    color={scorecard.data_accuracy > 90 ? "success" : scorecard.data_accuracy > 70 ? "warning" : "error"}
                    size="small"
                    sx={{ ml: 1 }}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>Error Rate</Typography>
                <Box display="flex" alignItems="center">
                  <Typography variant="h4">{scorecard.error_rate.toFixed(1)}%</Typography>
                  <Chip 
                    label={scorecard.error_rate < 10 ? "Low" : scorecard.error_rate < 30 ? "Medium" : "High"} 
                    color={scorecard.error_rate < 10 ? "success" : scorecard.error_rate < 30 ? "warning" : "error"}
                    size="small"
                    sx={{ ml: 1 }}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>Avg Response Time</Typography>
                <Typography variant="h4">
                  {scorecard.response_time < 1 
                    ? `${(scorecard.response_time * 60).toFixed(0)} mins` 
                    : `${scorecard.response_time.toFixed(1)} hrs`}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Submission stats */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Submission Statistics</Typography>
            <Divider sx={{ mb: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Total Submissions</Typography>
                    <Typography variant="h6">{scorecard.submission_stats.total}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Valid Submissions</Typography>
                    <Typography variant="h6">{scorecard.submission_stats.valid}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Invalid Submissions</Typography>
                    <Typography variant="h6">{scorecard.submission_stats.invalid}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Validity Rate</Typography>
                    <Typography variant="h6">{scorecard.submission_stats.validity_rate.toFixed(1)}%</Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Grid>

          {/* Charts */}
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Weekly Trends</Typography>
            <Box height={300}>
              <Line options={weeklyOptions} data={weeklyTrendData} />
            </Box>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Error Types</Typography>
            <Box height={300}>
              <Bar 
                data={errorTypeData} 
                options={{
                  indexAxis: 'y' as const,
                  responsive: true,
                }}
              />
            </Box>
          </Grid>

          {/* Error stats */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Error Statistics</Typography>
            <Divider sx={{ mb: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={6} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Total Errors</Typography>
                    <Typography variant="h6">{scorecard.error_stats.total_errors}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Total Warnings</Typography>
                    <Typography variant="h6">{scorecard.error_stats.total_warnings}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">Avg Errors per Submission</Typography>
                    <Typography variant="h6">
                      {scorecard.error_stats.avg_errors_per_submission.toFixed(2)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Grid>

          {/* Error Analytics */}
          <Grid item xs={12}>
            <VendorErrorAnalytics
              vendorName={scorecard.supplier_name}
              errorTrends={errorTrends}
              errorTypes={errorTypes}
              totalSubmissions={scorecard.submission_stats.total}
              errorRate={scorecard.error_rate}
            />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SupplierScorecard;