import { useState, useMemo, useCallback } from 'react';
import { VirtualFilesystem } from './core/filesystem';
import { SessionManager } from './core/session';
import { ProcessManager } from './core/process';
import { ConvexityExecutor } from './core/executor';
import { Header } from './components/Header';
import { TerminalView } from './components/TerminalView';
import { FileBrowserModal } from './components/FileBrowserModal';
import { ProcessModal } from './components/ProcessModal';
import { MapleModal } from './components/MapleModal';
import { HelpModal } from './components/HelpModal';

export default function App() {
  // Core singletons for the session lifetime
  const fs = useMemo(() => new VirtualFilesystem(), []);
  const sessionManager = useMemo(() => new SessionManager(), []);
  const processManager = useMemo(() => new ProcessManager(), []);
  const executor = useMemo(
    () => new ConvexityExecutor(fs, sessionManager, processManager),
    [fs, sessionManager, processManager]
  );

  // Trigger state to re-render when sessions change
  const [, setSessionTick] = useState(0);
  const triggerRefresh = useCallback(() => setSessionTick((t) => t + 1), []);

  // Active modals
  const [showFiles, setShowFiles] = useState(false);
  const [showProcesses, setShowProcesses] = useState(false);
  const [showMaple, setShowMaple] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const activeSession = sessionManager.getActiveSession();
  const sessions = sessionManager.listSessions();

  const handleSelectSession = (id: string) => {
    sessionManager.switchSession(id);
    triggerRefresh();
  };

  const handleCreateSession = () => {
    sessionManager.createSession();
    triggerRefresh();
  };

  const handleCloseSession = (id: string) => {
    sessionManager.removeSession(id);
    triggerRefresh();
  };

  const handleToggleMaple = () => {
    sessionManager.setMapleLoaded(activeSession.sessionId, !activeSession.mapleLoaded);
    triggerRefresh();
  };

  const handleRecordHistory = (command: string, exitCode?: number, duration?: number) => {
    sessionManager.addHistory(activeSession.sessionId, command, exitCode, duration);
    triggerRefresh();
  };

  const handleNavigateToDir = (newPath: string) => {
    sessionManager.setCwd(activeSession.sessionId, newPath);
    triggerRefresh();
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090d13] text-neutral-100 overflow-hidden font-mono">
      {/* Top Navigation & Status */}
      <Header
        sessions={sessions}
        activeSession={activeSession}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
        onCloseSession={handleCloseSession}
        onToggleMaple={handleToggleMaple}
        onOpenFiles={() => setShowFiles(true)}
        onOpenProcesses={() => setShowProcesses(true)}
        onOpenMaple={() => setShowMaple(true)}
        onOpenHelp={() => setShowHelp(true)}
      />

      {/* Main Terminal View */}
      <main className="flex-1 overflow-hidden relative">
        <TerminalView
          key={activeSession.sessionId}
          session={activeSession}
          executor={executor}
          fs={fs}
          onRecordHistory={handleRecordHistory}
          onCwdChange={handleNavigateToDir}
        />
      </main>

      {/* Modals */}
      {showFiles && (
        <FileBrowserModal
          fs={fs}
          currentCwd={activeSession.cwd}
          onClose={() => setShowFiles(false)}
          onNavigateToDir={handleNavigateToDir}
        />
      )}

      {showProcesses && (
        <ProcessModal
          processManager={processManager}
          onClose={() => setShowProcesses(false)}
        />
      )}

      {showMaple && (
        <MapleModal
          session={activeSession}
          onToggleMaple={handleToggleMaple}
          onRunCommand={(cmd) => {
            executor.execute(cmd, activeSession);
            sessionManager.addHistory(activeSession.sessionId, cmd);
            triggerRefresh();
          }}
          onClose={() => setShowMaple(false)}
        />
      )}

      {showHelp && (
        <HelpModal
          onClose={() => setShowHelp(false)}
          onRunCommand={(cmd) => {
            executor.execute(cmd, activeSession);
            sessionManager.addHistory(activeSession.sessionId, cmd);
            triggerRefresh();
          }}
        />
      )}
    </div>
  );
}
