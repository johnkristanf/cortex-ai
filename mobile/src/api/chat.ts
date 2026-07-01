import { apiClient } from './client';

export const chatApi = {
  sendMessage(
    message: string, 
    thread_id: string = "default", 
    google_access_token: string | null = null,
    onProgress?: (textChunk: string) => void
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      // Use XMLHttpRequest for streaming support in React Native
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${apiClient.defaults.baseURL}/chat`);
      xhr.setRequestHeader('Content-Type', 'application/json');
      
      let fullResponse = '';
      let processedLength = 0;

      xhr.onprogress = (event) => {
        const newData = xhr.responseText.substring(processedLength);
        processedLength = xhr.responseText.length;
        
        // SSE responses look like "data: {...}\n\n"
        const chunks = newData.split('\n\n');
        for (const chunk of chunks) {
          if (chunk.startsWith('data: ')) {
            const dataStr = chunk.substring(6);
            try {
              const data = JSON.parse(dataStr);
              if (data.error) {
                reject(new Error(data.error));
              } else if (data.text) {
                fullResponse += data.text;
                if (onProgress) onProgress(data.text);
              } else if (data.done) {
                // Done event, do nothing here. The onload will resolve it.
              }
            } catch (e) {
              // Not valid JSON or incomplete chunk, ignore
            }
          }
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(fullResponse);
        } else {
          reject(new Error(`Request failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error occurred'));
      };

      xhr.send(JSON.stringify({
        message,
        thread_id,
        google_access_token,
      }));
    });
  },

  async subscribeToDrive(
    user_id: string,
    folder_id: string,
    google_access_token: string,
    thread_id: string = "default"
  ) {
    const response = await apiClient.post('/drive/subscribe', {
      user_id,
      folder_id,
      google_access_token,
      thread_id,
    });
    return response.data;
  },
};
