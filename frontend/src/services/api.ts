import axios, { AxiosInstance } from 'axios';
import { ChatMessage, EditStyle } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

class APIService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // ====== COMMANDES ======

  async sendCommand(text: string, style?: EditStyle, context?: any) {
    try {
      const response = await this.api.post('/command', {
        text,
        style,
        context,
      });
      return response.data;
    } catch (error) {
      console.error('Erreur commande:', error);
      throw error;
    }
  }

  async sendQuickCommand(text: string, style?: EditStyle) {
    try {
      const response = await this.api.post('/command/quick', null, {
        params: { text, style },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur commande rapide:', error);
      throw error;
    }
  }

  // ====== VIDÉO ======

  async uploadVideo(file: File) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await this.api.post('/video/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur upload vidéo:', error);
      throw error;
    }
  }

  // ====== PRESETS ======

  async listPresets() {
    try {
      const response = await this.api.get('/presets');
      return response.data;
    } catch (error) {
      console.error('Erreur liste presets:', error);
      throw error;
    }
  }

  async applyPreset(name: string, layer: string) {
    try {
      const response = await this.api.post('/preset/apply', null, {
        params: { name, layer },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur appliquer preset:', error);
      throw error;
    }
  }

  // ====== STATUS ======

  async getStatus() {
    try {
      const response = await this.api.get('/status');
      return response.data;
    } catch (error) {
      console.error('Erreur statut:', error);
      throw error;
    }
  }

  async setAutoExecute(enabled: boolean) {
    try {
      const response = await this.api.post('/settings/auto-execute', null, {
        params: { enabled },
      });
      return response.data;
    } catch (error) {
      console.error('Erreur settings:', error);
      throw error;
    }
  }

  async healthCheck() {
    try {
      const response = await this.api.get('/health');
      return response.data;
    } catch (error) {
      console.error('Erreur health check:', error);
      throw error;
    }
  }

  async clearHistory() {
    try {
      const response = await this.api.post('/clear-history');
      return response.data;
    } catch (error) {
      console.error('Erreur clear history:', error);
      throw error;
    }
  }
}

export const apiService = new APIService();
