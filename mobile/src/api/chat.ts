import { apiClient } from './client';

export const chatApi = {
  async sendMessage(message: string, thread_id: string = "default"): Promise<string> {
    try {
      const response = await apiClient.post('/chat', {
        message,
        thread_id,
      });
      return response.data.response;
    } catch (error) {
      console.error('Error calling chat API:', error);
      throw error;
    }
  },
};
