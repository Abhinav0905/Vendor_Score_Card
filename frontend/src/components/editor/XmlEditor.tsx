import React, { useRef, useEffect, useState } from 'react';
import { Box, Button, CircularProgress, Alert, Typography } from '@mui/material';
import Editor, { Monaco } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import api from '../../services/api';

interface XmlEditorProps {
  submissionId: string;
  fileName: string;
  validationErrors?: any[];
  onSave?: (success: boolean, newSubmissionId?: string) => void;
}

const XmlEditor: React.FC<XmlEditorProps> = ({ 
  submissionId, 
  fileName,
  validationErrors = [],
  onSave
}) => {
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);

  // Fetch the file content
  useEffect(() => {
    const fetchFileContent = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const response = await api.getSubmissionContent(submissionId);
        
        if (response.success && response.file_content) {
          setFileContent(response.file_content);
        } else {
          setError(response.message || 'Failed to load file content');
        }
      } catch (err) {
        console.error('Error fetching file content:', err);
        setError('Failed to load file content. Please try again later.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchFileContent();
  }, [submissionId]);
  
  // Handle editor mounting
  const handleEditorDidMount = (editor: monaco.editor.IStandaloneCodeEditor, monaco: Monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    
    // Configure XML language features if needed
    monaco.languages.registerDocumentFormattingEditProvider('xml', {
      provideDocumentFormattingEdits: (model) => {
        // This is a simple XML formatter - for production you might want a more robust solution
        const text = model.getValue();
        let formatted = '';
        let indent = 0;
        let inTag = false;
        
        for (let i = 0; i < text.length; i++) {
          const char = text[i];
          
          if (char === '<' && text[i+1] !== '/') {
            formatted += '\n' + ' '.repeat(indent) + char;
            indent += 2;
            inTag = true;
          } else if (char === '<' && text[i+1] === '/') {
            indent -= 2;
            formatted += '\n' + ' '.repeat(indent) + char;
            inTag = true;
          } else if (char === '>') {
            formatted += char;
            inTag = false;
          } else if (!inTag && char === '\n') {
            // Skip extra newlines between tags
            continue;
          } else {
            formatted += char;
          }
        }
        
        return [{
          range: model.getFullModelRange(),
          text: formatted,
        }];
      }
    });
    
    // Add decorations for validation errors
    if (validationErrors && validationErrors.length > 0) {
      const decorations = validationErrors
        .filter(err => err.line_number)
        .map(err => {
          const lineNumber = err.line_number || 1;
          return {
            range: new monaco.Range(lineNumber, 1, lineNumber, 1),
            options: {
              isWholeLine: true,
              linesDecorationsClassName: err.severity === 'error' ? 'errorLineDecoration' : 'warningLineDecoration',
              hoverMessage: { value: err.message }
            }
          };
        });
        
      if (decorations.length > 0) {
        editor.deltaDecorations([], decorations);
      }
      
      // Add CSS for decorations
      const style = document.createElement('style');
      style.innerHTML = `
        .errorLineDecoration {
          background: rgba(255, 0, 0, 0.2);
          width: 5px !important;
          margin-left: 3px;
        }
        .warningLineDecoration {
          background: rgba(255, 165, 0, 0.2);
          width: 5px !important;
          margin-left: 3px;
        }
      `;
      document.head.appendChild(style);
    }
  };
  
  const handleSaveChanges = async () => {
    if (!editorRef.current) return;
    
    try {
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(false);
      
      const updatedContent = editorRef.current.getValue();
      const response = await api.updateSubmissionContent(submissionId, updatedContent);
      
      if (response.success) {
        setSaveSuccess(true);
        if (onSave) onSave(true, response.submission_id);
      } else {
        setSaveError(response.message || 'Failed to save changes');
        if (onSave) onSave(false);
      }
    } catch (err: any) {
      console.error('Error saving file:', err);
      setSaveError(err.message || 'Failed to save changes');
      if (onSave) onSave(false);
    } finally {
      setSaving(false);
    }
  };
  
  const formatDocument = () => {
    if (!editorRef.current || !monacoRef.current) return;
    
    editorRef.current.getAction('editor.action.formatDocument')?.run();
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        mb: 1,
        p: 1,
        borderBottom: 1,
        borderColor: 'divider'
      }}>
        <Typography variant="subtitle1">
          Editing: {fileName}
        </Typography>
        <Box>
          <Button 
            variant="outlined" 
            size="small" 
            onClick={formatDocument}
            sx={{ mr: 1 }}
          >
            Format XML
          </Button>
          <Button 
            variant="contained" 
            size="small"
            onClick={handleSaveChanges}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save & Validate'}
          </Button>
        </Box>
      </Box>
      
      {saveSuccess && (
        <Alert severity="success" sx={{ mb: 1 }}>
          Changes saved successfully. File is being revalidated.
        </Alert>
      )}
      
      {saveError && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {saveError}
        </Alert>
      )}
      
      {loading ? (
        <Box display="flex" justifyContent="center" alignItems="center" flexGrow={1}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error" sx={{ m: 2 }}>
          {error}
        </Alert>
      ) : (
        <Box sx={{ flexGrow: 1, border: 1, borderColor: 'divider' }}>
          <Editor
            height="100%"
            language="xml"
            theme="vs-light"
            value={fileContent}
            options={{
              minimap: { enabled: true },
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: 'on',
              wrappingIndent: 'same'
            }}
            onMount={handleEditorDidMount}
          />
        </Box>
      )}
    </Box>
  );
};

export default XmlEditor;