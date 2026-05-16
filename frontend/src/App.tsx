import { useState } from 'react';
import { AECommand } from './types';
import { Chat } from './components/Chat';
import { StatusBar } from './components/StatusBar';
import { VideoUpload } from './components/VideoUpload';
import { Console } from './components/Console';
import './index.css';

function App() {
  const [currentCommands, setCurrentCommands] = useState<AECommand[]>([]);
  const [videoInfo, setVideoInfo] = useState<{ filename: string; filepath: string } | null>(null);

  const handleCommandExecuted = (commands: AECommand[]) => {
    setCurrentCommands(commands);
  };

  const handleVideoUpload = (filename: string, filepath: string) => {
    setVideoInfo({ filename, filepath });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary to-dark text-white px-6 py-4">
        <h1 className="text-3xl font-bold">ÉDITSENSEI AI</h1>
        <p className="text-sm opacity-90">Assistant IA pour Adobe After Effects</p>
      </div>

      {/* Status Bar */}
      <StatusBar />

      {/* Main Layout */}
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-3 gap-4 p-4">
        {/* Colonne gauche - Chat */}
        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Chat onCommandExecuted={handleCommandExecuted} />
        </div>

        {/* Colonne droite - Outils */}
        <div className="flex flex-col gap-4 min-h-0 overflow-y-auto">
          {/* Upload vidéo */}
          <div className="bg-white rounded-lg p-4 shadow">
            <h3 className="font-bold text-dark mb-3">Vidéo</h3>
            <VideoUpload onUploadSuccess={handleVideoUpload} />
            {videoInfo && (
              <div className="mt-3 p-2 bg-light rounded text-sm">
                <p className="text-green-700">✓ {videoInfo.filename}</p>
              </div>
            )}
          </div>

          {/* Presets */}
          <div className="bg-white rounded-lg p-4 shadow">
            <h3 className="font-bold text-dark mb-3">Presets Rapides</h3>
            <div className="space-y-2">
              {['aggressive', 'smooth', 'anime', 'gaming'].map((preset) => (
                <button
                  key={preset}
                  className="w-full px-3 py-2 bg-primary text-white rounded hover:bg-opacity-80 text-sm font-medium transition"
                >
                  {preset.charAt(0).toUpperCase() + preset.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Console */}
          <div className="flex-1 min-h-0">
            <Console commands={currentCommands} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
