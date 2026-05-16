export type EditStyle = 'aggressive' | 'smooth' | 'anime' | 'gaming' | 'cinematic';

export interface AECommand {
  action: string;
  layer?: string;
  property?: string;
  value?: any;
  duration?: number;
}

export interface AIResponse {
  success: boolean;
  message: string;
  ae_commands?: AECommand[];
  ae_responses?: AEResponse[];
  confidence?: number;
}

export interface AEResponse {
  success: boolean;
  message: string;
  data?: any;
}

export interface VideoAnalysis {
  duration: number;
  fps: number;
  resolution: string;
  beats: number[];
  transitions: any[];
  motion_intensity: number;
  dominant_colors: string[];
  suggested_style: EditStyle;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
  ae_actions?: AECommand[];
}

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp?: number;
}

export interface AppStatus {
  ae_connected: boolean;
  frontend_connected: boolean;
  current_command?: string;
  last_error?: string;
}
