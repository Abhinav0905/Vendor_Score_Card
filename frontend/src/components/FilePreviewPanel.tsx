import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Chip,
  CircularProgress,
  Alert,
  Collapse,
  Divider
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { ValidationError } from '../types/supplier';
import axios from 'axios';

interface FilePreviewPanelProps {
  submissionId: string;
  fileName: string;
}

interface ValidationResult {
  errors: ValidationError[];
  status: string;
  error_count: number;
  warning_count: number;
}

const FilePreviewPanel: React.FC<FilePreviewPanelProps> = ({ submissionId, fileName }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [expandedErrors, setExpandedErrors] = useState<Record<string, boolean>>({});
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    let mounted = true;
    let pollingTimeout: NodeJS.Timeout;

    const fetchValidationResults = async () => {
      try {
        if (!mounted) return;

        const response = await axios.get(`http://localhost:8000/epcis/submissions/${submissionId}/validation`);
        if (!mounted) return;

        if (response.data && response.data.errors) {
          setValidationResult(response.data);

          // If validation is complete, stop polling
          if (response.data.status === 'VALIDATED' || response.data.status === 'FAILED') {
            setIsPolling(false);
          } else if (isPolling) {
            // Continue polling only if still needed
            pollingTimeout = setTimeout(fetchValidationResults, 2000);
          }
        }
      } catch (err: any) {
        if (!mounted) return;
        console.error('Error fetching validation results:', err);
        setError(err.response?.data?.message || 'Failed to fetch validation results');
        setIsPolling(false);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    // Start fetching results
    fetchValidationResults();
    setIsPolling(true);

    return () => {
      mounted = false;
      clearTimeout(pollingTimeout);
    };
  }, [submissionId]);

  const toggleErrorExpansion = (errorId: string) => {
    setExpandedErrors(prev => ({
      ...prev,
      [errorId]: !prev[errorId]
    }));
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getErrorTypeLabel = (type: string): string => {
    switch (type.toLowerCase()) {
      case 'structure':
        return 'Structure Validation';
      case 'field':
        return 'Field Validation';
      case 'sequence':
        return 'Sequence Validation';
      case 'aggregation':
        return 'Aggregation Validation';
      default:
        return type.charAt(0).toUpperCase() + type.slice(1);
    }
  };

  const summarizeErrors = (errors: ValidationError[]) => {
    // Group errors by type and message pattern
    const errorGroups: Record<string, {
      type: string,
      severity: string,
      baseMessage: string,
      lineNumber: number,
      count: number,
      examples: string[]
    }> = {};

    errors.forEach(error => {
      // If the error already has a count, it's an aggregated error
      if ('count' in error) {
        const key = `${error.type}-${error.message}-${error.severity}`;
        if (!errorGroups[key]) {
          errorGroups[key] = {
            type: error.type,
            severity: error.severity,
            baseMessage: error.message,
            lineNumber: error.line_number || 0,
            count: error.count,
            examples: []
          };
        }
        return;
      }

      // For non-aggregated errors, extract the base message pattern
      const messageParts = error.message.split('for urn:epc:');
      const baseMessage = messageParts[0].trim();
      const identifier = messageParts[1] ? 'urn:epc:' + messageParts[1].trim() : '';

      // Use a key combining type, base message, and severity for grouping
      const key = `${error.type}-${baseMessage}-${error.severity}`;

      if (!errorGroups[key]) {
        errorGroups[key] = {
          type: error.type,
          severity: error.severity,
          baseMessage: baseMessage,
          lineNumber: error.line_number || 0,
          count: 0,
          examples: []
        };
      }

      errorGroups[key].count++;
      if (errorGroups[key].examples.length < 3 && identifier) {
        errorGroups[key].examples.push(identifier);
      }
    });

    return Object.values(errorGroups);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!validationResult) {
    return (
      <Alert severity="info">
        No validation results available.
      </Alert>
    );
  }

  const { errors } = validationResult;
  const summarizedErrors = summarizeErrors(errors);

  // Group summarized errors by type
  const errorsByType = summarizedErrors.reduce((acc, error) => {
    const key = error.type;
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(error);
    return acc;
  }, {} as Record<string, typeof summarizedErrors>);

  // Sort error types
  const errorTypes = Object.keys(errorsByType).sort((a, b) => {
    const order = ['structure', 'field', 'sequence', 'aggregation'];
    return order.indexOf(a) - order.indexOf(b);
  });

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Validation Results for {fileName}
      </Typography>

      {errors.length === 0 ? (
        <Alert severity="success">
          No validation errors found in the file.
        </Alert>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Found {errors.filter(e => e.severity === 'error').length} errors and {errors.filter(e => e.severity === 'warning').length} warnings
          </Typography>

          {errorTypes.map(type => {
            const typeErrors = errorsByType[type];
            const errorCount = errors.filter(e => e.type === type && e.severity === 'error').length;
            const warningCount = errors.filter(e => e.type === type && e.severity === 'warning').length;

            return (
              <Paper key={type} sx={{ mb: 2, overflow: 'hidden' }}>
                <Box sx={{ bgcolor: 'primary.main', p: 1, color: 'white' }}>
                  <Typography variant="subtitle1">
                    {getErrorTypeLabel(type)} ({errorCount > 0 ? `${errorCount} errors` : ''}{errorCount > 0 && warningCount > 0 ? ', ' : ''}{warningCount > 0 ? `${warningCount} warnings` : ''})
                  </Typography>
                </Box>
                <List dense>
                  {typeErrors.map((error, index) => (
                    <React.Fragment key={index}>
                      <ListItem
                        sx={{ cursor: 'pointer' }}
                        onClick={() => toggleErrorExpansion(`${type}-${index}`)}
                      >
                        <ListItemText
                          primary={
                            <Box display="flex" alignItems="center" gap={1}>
                              <Chip
                                label={error.severity}
                                color={getSeverityColor(error.severity)}
                                size="small"
                              />
                              <Typography variant="body2" sx={{ flex: 1 }}>
                                {error.baseMessage}
                                <Typography component="span" color="text.secondary">
                                  ({error.count} items)
                                </Typography>
                                {error.lineNumber > 0 && (
                                  <Typography component="span" color="text.secondary">
                                    {" "}(Line {error.lineNumber})
                                  </Typography>
                                )}
                              </Typography>
                              {expandedErrors[`${type}-${index}`] ? (
                                <ExpandLessIcon fontSize="small" />
                              ) : (
                                <ExpandMoreIcon fontSize="small" />
                              )}
                            </Box>
                          }
                        />
                      </ListItem>
                      <Collapse in={expandedErrors[`${type}-${index}`]}>
                        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
                          <Typography variant="body2" gutterBottom>
                            Affects {error.count} items
                          </Typography>
                          {error.examples.length > 0 && (
                            <>
                              <Typography variant="body2" gutterBottom>
                                Examples:
                              </Typography>
                              {error.examples.map((example, i) => (
                                <Typography
                                  key={i}
                                  variant="body2"
                                  component="pre"
                                  sx={{
                                    whiteSpace: 'pre-wrap',
                                    fontFamily: 'monospace',
                                    fontSize: '0.875rem',
                                    ml: 2
                                  }}
                                >
                                  {example}
                                </Typography>
                              ))}
                              {error.count > error.examples.length && (
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                  ...and {error.count - error.examples.length} more
                                </Typography>
                              )}
                            </>
                          )}
                        </Box>
                      </Collapse>
                      <Divider />
                    </React.Fragment>
                  ))}
                </List>
              </Paper>
            );
          })}
        </>
      )}
    </Box>
  );
};

export default FilePreviewPanel;