import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  CircularProgress,
  Chip,
  Card,
  CardContent,
  Alert
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import SendIcon from '@mui/icons-material/Send';
import api from '../../services/api';

interface QueryInputProps {
  onQueryComplete?: (result: any) => void;
}

const QueryInput: React.FC<QueryInputProps> = ({ onQueryComplete }) => {
  const [query, setQuery] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);

  const handleQueryChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  };

  const processQuery = async () => {
    if (!query.trim()) return;

    try {
      setIsProcessing(true);
      setError(null);

      // Example queries that return mock responses
      let mockResult;
      const lowerQuery = query.toLowerCase();

      if (lowerQuery.includes('highest error rate')) {
        mockResult = {
          type: 'supplier_ranking',
          title: 'Suppliers with Highest Error Rate',
          data: [
            { name: 'Supplier B', error_rate: 15.2 },
            { name: 'Supplier D', error_rate: 12.7 },
            { name: 'Supplier A', error_rate: 8.5 },
          ]
        };
      } else if (lowerQuery.includes('common error')) {
        mockResult = {
          type: 'error_analysis',
          title: 'Most Common Error Types',
          data: [
            { type: 'Field Validation', count: 35, percentage: 48.6 },
            { type: 'Sequence Validation', count: 18, percentage: 25.0 },
            { type: 'Structure', count: 12, percentage: 16.7 },
            { type: 'Aggregation', count: 7, percentage: 9.7 }
          ]
        };
      } else if (lowerQuery.includes('performance trend')) {
        mockResult = {
          type: 'trend_analysis',
          title: 'Performance Trend Last 4 Weeks',
          data: [
            { week: 'Week -4', submissions: 28, errors: 5 },
            { week: 'Week -3', submissions: 32, errors: 4 },
            { week: 'Week -2', submissions: 30, errors: 3 },
            { week: 'Week -1', submissions: 35, errors: 3 }
          ]
        };
      } else {
        mockResult = {
          type: 'general_info',
          title: 'General Information',
          data: 'I found 125 total EPCIS submissions with a success rate of 78.4% over the last 30 days.'
        };
      }

      // In a real implementation, we would call the API instead
      // const response = await api.processQuery(query);
      // const result = response;

      setResult(mockResult);
      
      // Add to recent queries if not already there
      if (!recentQueries.includes(query)) {
        setRecentQueries(prev => [query, ...prev.slice(0, 4)]);
      }

      if (onQueryComplete) {
        onQueryComplete(mockResult);
      }
    } catch (err) {
      console.error('Error processing query:', err);
      setError('Failed to process your query. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRecentQueryClick = (recentQuery: string) => {
    setQuery(recentQuery);
  };

  const renderQueryResult = () => {
    if (!result) return null;

    switch (result.type) {
      case 'supplier_ranking':
        return (
          <Card variant="outlined" sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6">{result.title}</Typography>
              {result.data.map((item: any, idx: number) => (
                <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', my: 1 }}>
                  <Typography>{item.name}</Typography>
                  <Typography color="error">{item.error_rate}%</Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        );
      case 'error_analysis':
        return (
          <Card variant="outlined" sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6">{result.title}</Typography>
              {result.data.map((item: any, idx: number) => (
                <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', my: 1 }}>
                  <Typography>{item.type}</Typography>
                  <Box>
                    <Typography component="span">{item.count} errors</Typography>
                    <Typography component="span" color="text.secondary" sx={{ ml: 1 }}>
                      ({item.percentage}%)
                    </Typography>
                  </Box>
                </Box>
              ))}
            </CardContent>
          </Card>
        );
      case 'trend_analysis':
        return (
          <Card variant="outlined" sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6">{result.title}</Typography>
              <Box sx={{ mt: 1 }}>
                {result.data.map((item: any, idx: number) => (
                  <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', my: 1 }}>
                    <Typography>{item.week}</Typography>
                    <Box>
                      <Typography component="span">{item.submissions} submissions,</Typography>
                      <Typography component="span" color="error" sx={{ ml: 1 }}>
                        {item.errors} errors
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        );
      case 'general_info':
      default:
        return (
          <Card variant="outlined" sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6">{result.title}</Typography>
              <Typography sx={{ mt: 1 }}>{result.data}</Typography>
            </CardContent>
          </Card>
        );
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom display="flex" alignItems="center">
        <SearchIcon sx={{ mr: 1 }} />
        NLP Search
      </Typography>
      
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Ask questions in natural language about your supplier scorecard data
      </Typography>
      
      <Box sx={{ display: 'flex', mt: 2 }}>
        <TextField
          fullWidth
          placeholder="e.g., 'Which suppliers have the highest error rate?' or 'What are the most common errors?'"
          value={query}
          onChange={handleQueryChange}
          variant="outlined"
          disabled={isProcessing}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              processQuery();
            }
          }}
        />
        <Button
          variant="contained"
          color="primary"
          onClick={processQuery}
          disabled={!query.trim() || isProcessing}
          sx={{ ml: 1, minWidth: '100px' }}
          endIcon={isProcessing ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
        >
          {isProcessing ? 'Processing' : 'Ask'}
        </Button>
      </Box>

      {/* Recent queries chips */}
      {recentQueries.length > 0 && (
        <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
            Recent:
          </Typography>
          {recentQueries.map((recentQuery, idx) => (
            <Chip
              key={idx}
              label={recentQuery.length > 30 ? `${recentQuery.substring(0, 30)}...` : recentQuery}
              onClick={() => handleRecentQueryClick(recentQuery)}
              size="small"
              variant="outlined"
            />
          ))}
        </Box>
      )}

      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      {/* Query result */}
      {renderQueryResult()}
    </Paper>
  );
};

export default QueryInput;