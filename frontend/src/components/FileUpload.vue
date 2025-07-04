<template>
  <div class="file-upload">
    <div class="upload-zone" @drop.prevent="handleDrop" @dragover.prevent>
      <input type="file" @change="handleFileUpload" accept=".xml,.json" />
      <p>Drop your EPCIS file here or click to browse</p>
    </div>
    
    <div v-if="errorMessage" class="error-message">
      <pre>{{ errorMessage }}</pre>
    </div>
    
    <div v-if="uploadStatus" class="status-message" :class="uploadStatus.type">
      {{ uploadStatus.message }}
    </div>
  </div>
</template>

<script>
import { uploadEPCISFile } from '../api';

export default {
  name: 'FileUpload',
  data() {
    return {
      errorMessage: null,
      uploadStatus: null
    };
  },
  methods: {
    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        await this.uploadFile(file);
      }
    },
    
    handleDrop(event) {
      const file = event.dataTransfer.files[0];
      if (file) {
        this.uploadFile(file);
      }
    },
    
    async uploadFile(file) {
      this.errorMessage = null;
      this.uploadStatus = { type: 'info', message: 'Uploading file...' };
      
      const formData = new FormData();
      formData.append('file', file);
      
      try {
        const response = await fetch('epcis/upload', {
          method: 'POST',
          body: formData,
        });
        
        const data = await response.json();
        
        if (response.status === 409) {
          // Format duplicate submission error
          let errorMsg = 'Duplicate Submission Detected\n\n';
          
          if (data.detail && data.detail.original_submission) {
            const orig = data.detail.original_submission;
            errorMsg += `Original Submission Details:\n`;
            errorMsg += `File: ${orig.file_name}\n`;
            errorMsg += `Date: ${new Date(orig.submission_date).toLocaleString()}\n`;
            errorMsg += `Status: ${orig.status}\n`;
            
            if (orig.instance_identifier) {
              errorMsg += `Instance ID: ${orig.instance_identifier}\n`;
            }
            
            if (data.detail.duplicate_type) {
              errorMsg += `\nDetected by: ${data.detail.duplicate_type === 'instance_identifier' ? 
                'Document Instance ID' : 'File Content Hash'}`;
            }
          }
          
          this.errorMessage = errorMsg;
          this.uploadStatus = { type: 'error', message: 'Upload failed - Duplicate file' };
          return;
        }
        
        if (!response.ok) {
          throw new Error(`Upload failed: ${data.message || 'Unknown error'}`);
        }
        
        this.uploadStatus = { type: 'success', message: 'File uploaded successfully' };
        this.$emit('upload-success', data);
        
      } catch (error) {
        this.errorMessage = `Error: ${error.message}`;
        this.uploadStatus = { type: 'error', message: 'Upload failed' };
      }
    }
  }
};
</script>

<style scoped>
.file-upload {
  padding: 20px;
}

.upload-zone {
  border: 2px dashed #ccc;
  padding: 20px;
  text-align: center;
  margin-bottom: 15px;
  cursor: pointer;
}

.error-message {
  background-color: #ffebee;
  color: #d32f2f;
  padding: 15px;
  margin: 10px 0;
  border-radius: 4px;
  white-space: pre-wrap;
  font-family: monospace;
}

.status-message {
  padding: 10px;
  margin: 10px 0;
  border-radius: 4px;
}

.status-message.error {
  background-color: #ffebee;
  color: #d32f2f;
}

.status-message.success {
  background-color: #e8f5e9;
  color: #2e7d32;
}

.status-message.info {
  background-color: #e3f2fd;
  color: #1976d2;
}
</style>