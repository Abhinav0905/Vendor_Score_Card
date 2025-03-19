import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Divider,
  List,
  ListItem,
  ListItemText,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  Collapse
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { ValidationError } from '../types/supplier';
import api from '../services/api';

interface ValidationErrorsListProps {
  errors: ValidationError[];
  submissionId: string;
  onErrorResolved?: () => void;
}

const ValidationErrorsList: React.FC<ValidationErrorsListProps> = ({ 
  errors, 
  submissionId,
  onErrorResolved 
}) => {
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedError, setSelectedError] = useState<ValidationError | null>(null);
  const [resolutionNote, setResolutionNote] = useState('');
  const [resolvedBy, setResolvedBy] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [expandedErrors, setExpandedErrors] = useState<Record<string, boolean>>({});

  const handleOpenDialog = (error: ValidationError) => {
    setSelectedError(error);
    setOpenDialog(true);
    setResolutionNote('');
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setSelectedError(null);
  };

  const handleResolveError = async () => {
    if (!selectedError || !resolutionNote || !resolvedBy) return;
    
    try {
      setIsSubmitting(true);
      await api.resolveError(selectedError.id, resolutionNote, resolvedBy);
      handleCloseDialog();
      if (onErrorResolved) {
        onErrorResolved();
      }
    } catch (error) {
      console.error('Error resolving validation error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleErrorExpansion = (errorId: string) => {
    setExpandedErrors(prev => ({
      ...prev,
      [errorId]: !prev[errorId]
    }));
  };

  // Group errors by type for better organization
  const errorsByType = errors.reduce((acc, error) => {
    acc[error.type] = acc[error.type] || [];
    acc[error.type].push(error);
    return acc;
  }, {} as Record<string, ValidationError[]>);

  const errorTypeLabels: Record<string, string> = {
    'structure': 'Structure Errors',
    'field': 'Field Validation Errors',
    'sequence': 'Sequence Validation Errors',
    'aggregation': 'Aggregation Errors',
    'parse': 'Parsing Errors'
  };

  const errorTypePriority = ['structure', 'field', 'sequence', 'aggregation', 'parse'];
  
  // Sort error types by priority
  const sortedErrorTypes = Object.keys(errorsByType).sort(
    (a, b) => errorTypePriority.indexOf(a) - errorTypePriority.indexOf(b)
  );

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

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Validation Results for Submission: {submissionId}
      </Typography>
      
      {errors.length === 0 ? (
        <Paper sx={{ p: 2, textAlign: 'center' }}>
          <Typography>No validation errors found.</Typography>
        </Paper>
      ) : (
        <>
          <Typography variant="body2" color="textSecondary" gutterBottom>
            {errors.filter(e => !e.is_resolved).length} unresolved issues found
          </Typography>
          
          {sortedErrorTypes.map(errorType => (
            <Paper key={errorType} sx={{ mb: 2, overflow: 'hidden' }}>
              <Box sx={{ bgcolor: 'primary.main', p: 1, color: 'white' }}>
                <Typography variant="subtitle1">
                  {errorTypeLabels[errorType] || errorType} ({errorsByType[errorType].length})
                </Typography>
              </Box>
              <Divider />
              
              <List dense sx={{ maxHeight: 300, overflow: 'auto' }}>
                {errorsByType[errorType].map(error => (
                  <React.Fragment key={error.id}>
                    <ListItem 
                      sx={{
                        opacity: error.is_resolved ? 0.6 : 1,
                        bgcolor: error.is_resolved ? 'rgba(0, 0, 0, 0.04)' : 'inherit',
                        cursor: 'pointer'
                      }}
                      onClick={() => toggleErrorExpansion(error.id)}
                    >
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Chip 
                              label={error.severity} 
                              color={getSeverityColor(error.severity)} 
                              size="small" 
                            />
                            <Typography variant="body2">
                              {error.message}
                              {error.line_number && (
                                <Typography component="span" color="text.secondary">
                                  {" "}(Line {error.line_number})
                                </Typography>
                              )}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Box display="flex" justifyContent="space-between" alignItems="center">
                            {error.is_resolved && error.resolution_note ? (
                              <Typography variant="caption" color="textSecondary">
                                Resolution: {error.resolution_note}
                              </Typography>
                            ) : null}
                            {expandedErrors[error.id] ? (
                              <ExpandLessIcon fontSize="small" />
                            ) : (
                              <ExpandMoreIcon fontSize="small" />
                            )}
                          </Box>
                        }
                      />
                      {!error.is_resolved && (
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDialog(error);
                          }}
                          sx={{ ml: 2 }}
                        >
                          Resolve
                        </Button>
                      )}
                    </ListItem>
                    <Collapse in={expandedErrors[error.id]}>
                      <Box sx={{ p: 2, bgcolor: 'background.default' }}>
                        <Typography variant="body2" component="pre" sx={{ 
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'monospace',
                          fontSize: '0.875rem'
                        }}>
                          {error.message}
                        </Typography>
                        {error.line_number && (
                          <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                            Location: Line {error.line_number}
                          </Typography>
                        )}
                      </Box>
                    </Collapse>
                    <Divider />
                  </React.Fragment>
                ))}
              </List>
            </Paper>
          ))}
        </>
      )}

      <Dialog open={openDialog} onClose={handleCloseDialog}>
        <DialogTitle>Resolve Error</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {selectedError?.message}
            {selectedError?.line_number && (
              <Typography variant="body2" color="text.secondary">
                Line: {selectedError.line_number}
              </Typography>
            )}
          </DialogContentText>
          
          <TextField
            autoFocus
            margin="dense"
            label="Your Name"
            fullWidth
            variant="outlined"
            value={resolvedBy}
            onChange={(e) => setResolvedBy(e.target.value)}
            sx={{ mb: 2 }}
          />
          
          <TextField
            margin="dense"
            label="Resolution Note"
            fullWidth
            variant="outlined"
            multiline
            rows={4}
            value={resolutionNote}
            onChange={(e) => setResolutionNote(e.target.value)}
            helperText="Describe how you resolved this issue"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} color="primary">
            Cancel
          </Button>
          <Button 
            onClick={handleResolveError} 
            color="primary" 
            variant="contained"
            disabled={!resolutionNote || !resolvedBy || isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Mark as Resolved'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ValidationErrorsList;