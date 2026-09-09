import React from 'react';
import { Terminal, Bot, FolderTree, Cpu, Plus, Trash2, Sparkles, HelpCircle } from 'lucide-react';
import { TerminalSession } from '../types';

interface HeaderProps {
  sessions: TerminalSession[];
  activeSession: TerminalSession;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
  onCloseSession: (id: string) => void;
  onToggleMaple: () => void;
  onOpenFiles: () => void;
  onOpenProcesses: () => void;
  onOpenMaple: () => void;
  onOpenHelp: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  sessions,
  activeSession,
  onSelectSession,
  onCreateSession,
  onCloseSession,
  onToggleMaple,
  onOpenFiles,
  onOpenProcesses,
  onOpenMaple,
  onOpenHelp,
}) => {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-[#0d1117] border-b border-neutral-800/80 text-sm">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 font-semibold text-neutral-100 tracking-wide">
          <div className="w-7 h-7 rounded-md bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-sm">
            <Terminal className="w-4 h-4 text-white" />
          </div>
          <span className="text-base tracking-wider font-bold bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-indigo-300">
            CONVEXITY
          </span>
          <span className="px-1.5 py-0.5 rounded text-[11px] font-medium bg-neutral-800 text-neutral-400 border border-neutral-700">
            v1.2.0
          </span>
        </div>

        {/* Sessions tabs */}
        <div className="flex items-center gap-1 bg-[#161b22] p-1 rounded-md border border-neutral-800 max-w-md overflow-x-auto">
          {sessions.map((sess) => (
            <div
              key={sess.sessionId}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition cursor-pointer ${
                sess.sessionId === activeSession.sessionId
                  ? 'bg-[#21262d] text-sky-400 font-medium shadow-xs'
                  : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50'
              }`}
              onClick={() => onSelectSession(sess.sessionId)}
            >
              <span>{sess.name}</span>
              {sessions.length > 1 && (
                <button
                  type="button"
                  title="Close session"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCloseSession(sess.sessionId);
                  }}
                  className="hover:text-rose-400 p-0.5 rounded"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}

          <button
            type="button"
            onClick={onCreateSession}
            title="New Terminal Session"
            className="p-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Maple status toggle */}
        <button
          type="button"
          onClick={onToggleMaple}
          className={`flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-medium border transition ${
            activeSession.mapleLoaded
              ? 'bg-indigo-950/50 border-indigo-600/60 text-indigo-300 shadow-[0_0_12px_rgba(99,102,241,0.25)]'
              : 'bg-neutral-800/60 border-neutral-700 text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Bot className={`w-3.5 h-3.5 ${activeSession.mapleLoaded ? 'text-indigo-400 animate-pulse' : ''}`} />
          <span>Maple: {activeSession.mapleLoaded ? 'ACTIVE' : 'OFF'}</span>
          <span
            className={`w-2 h-2 rounded-full ${
              activeSession.mapleLoaded ? 'bg-indigo-400' : 'bg-neutral-500'
            }`}
          />
        </button>

        {/* Quick toolbars */}
        <button
          type="button"
          onClick={onOpenFiles}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 border border-neutral-700 transition"
        >
          <FolderTree className="w-3.5 h-3.5 text-sky-400" />
          <span className="hidden sm:inline">Files</span>
        </button>

        <button
          type="button"
          onClick={onOpenProcesses}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 border border-neutral-700 transition"
        >
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden sm:inline">Processes</span>
        </button>

        <button
          type="button"
          onClick={onOpenMaple}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 border border-neutral-700 transition"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden sm:inline">Maple AI</span>
        </button>

        <button
          type="button"
          onClick={onOpenHelp}
          title="Terminal Manual"
          className="p-1.5 rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
