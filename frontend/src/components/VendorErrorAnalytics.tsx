import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  useTheme
} from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface ErrorTrend {
  date: string;
  errorCount: number;
  errorRate: number;
}

interface ErrorType {
  type: string;
  count: number;
  severity: 'error' | 'warning';
}

interface VendorErrorAnalyticsProps {
  vendorName: string;
  errorTrends: ErrorTrend[];
  errorTypes: ErrorType[];
  totalSubmissions: number;
  errorRate: number;
}

const VendorErrorAnalytics: React.FC<VendorErrorAnalyticsProps> = ({
  vendorName,
  errorTrends,
  errorTypes,
  totalSubmissions,
  errorRate
}) => {
  const theme = useTheme();

  const trendData = {
    labels: errorTrends.map(trend => trend.date),
    datasets: [
      {
        label: 'Error Count',
        data: errorTrends.map(trend => trend.errorCount),
        borderColor: theme.palette.error.main,
        backgroundColor: theme.palette.error.light,
        yAxisID: 'y',
      },
      {
        label: 'Error Rate (%)',
        data: errorTrends.map(trend => trend.errorRate),
        borderColor: theme.palette.warning.main,
        backgroundColor: theme.palette.warning.light,
        yAxisID: 'y1',
      }
    ]
  };

  const trendOptions = {
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
          text: 'Error Count'
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
          text: 'Error Rate (%)'
        }
      },
    },
  };

  const errorTypeData = {
    labels: errorTypes.map(error => error.type),
    datasets: [
      {
        label: 'Errors',
        data: errorTypes.filter(error => error.severity === 'error').map(error => error.count),
        backgroundColor: theme.palette.error.main,
      },
      {
        label: 'Warnings',
        data: errorTypes.filter(error => error.severity === 'warning').map(error => error.count),
        backgroundColor: theme.palette.warning.main,
      }
    ]
  };

  const errorTypeOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Count'
        }
      }
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Error Analytics for {vendorName}
      </Typography>
      
      <Box sx={{ mb: 4 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Total Submissions
            </Typography>
            <Typography variant="h4">
              {totalSubmissions}
            </Typography>
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Overall Error Rate
            </Typography>
            <Typography variant="h4" color={errorRate > 10 ? 'error.main' : 'success.main'}>
              {errorRate.toFixed(1)}%
            </Typography>
          </Grid>
        </Grid>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Error Trends Over Time
          </Typography>
          <Box height={300}>
            <Line data={trendData} options={trendOptions} />
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Error Type Distribution
          </Typography>
          <Box height={300}>
            <Bar data={errorTypeData} options={errorTypeOptions} />
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default VendorErrorAnalytics;