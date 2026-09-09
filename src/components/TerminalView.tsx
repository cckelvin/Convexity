import React, { useState, useRef, useEffect, useCallback } from 'react';
import { AlertTriangle, CornerDownLeft, ShieldAlert } from 'lucide-react';
import { TerminalSession, TerminalOutputLine, CommandResult } from '../types';
import { ConvexityExecutor } from '../core/executor';
import { VirtualFilesystem } from '../core/filesystem';

interface TerminalViewProps {
  session: TerminalSession;
  executor: ConvexityExecutor;
  fs: VirtualFilesystem;
  onRecordHistory: (command: string, exitCode?: number, duration?: number) => void;
  onCwdChange?: (newCwd: string) => void;
}

const BUILTIN_COMMANDS = [
  'help', 'pwd', 'cd', 'ls', 'cat', 'write', 'append', 'touch',
  'mkdir', 'rm', 'cp', 'mv', 'stat', 'exists', 'find', 'grep',
  'set', 'unset', 'env', 'alias', 'unalias', 'jobs', 'ps', 'kill',
  'run', 'whoami', 'hostname', 'sysinfo', 'load maple', 'kill maple',
  'maple', 'history', 'echo', 'clear', 'tools', 'libraries', 'exit'
];

export const TerminalView: React.FC<TerminalViewProps> = ({
  session,
  executor,
  fs,
  onRecordHistory,
}) => {
  const [lines, setLines] = useState<TerminalOutputLine[]>([
    {
      id: 'init-1',
      type: 'system',
      text: `CONVEXITY TERMINAL [Version 1.2.0 - Node Runtime Environment]
(c) 2026 Convexity AI Systems. All rights reserved.

Session initialized: ${session.sessionId}
Connected to virtual execution layer. Type 'help' or click quick actions below.`,
      timestamp: Date.now(),
    },
  ]);

  const [inputVal, setInputVal] = useState('');
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{
    command: string;
    reason: string;
    action: () => CommandResult;
  } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [lines, scrollToBottom]);

  // Focus input whenever terminal is clicked
  const handleContainerClick = () => {
    inputRef.current?.focus();
  };

  const getPromptString = () => {
    const cleanCwd = session.cwd.replace(/^\/home\/user/, '~');
    const mapleTag = session.mapleLoaded ? ' [Maple]' : '';
    return `convexity:${cleanCwd}${mapleTag}>`;
  };

  const executeCommand = (cmdStr: string, confirmed = false) => {
    const trimmed = cmdStr.trim();
    if (!trimmed) return;

    const currentPrompt = getPromptString();

    // Append command to output line
    const cmdLine: TerminalOutputLine = {
      id: 'cmd-' + Math.random().toString(36).substring(2, 9),
      type: 'command',
      text: trimmed,
      prompt: currentPrompt,
      timestamp: Date.now(),
    };

    const startTime = performance.now();
    const result = executor.execute(trimmed, session, confirmed);
    const duration = Math.round(performance.now() - startTime);

    onRecordHistory(trimmed, result.exitCode, duration);

    if (result.requiresConfirmation && result.pendingAction) {
      setPendingConfirm({
        command: trimmed,
        reason: result.confirmationReason || 'High-risk destructive command execution',
        action: result.pendingAction,
      });

      setLines((prev) => [
        ...prev,
        cmdLine,
        {
          id: 'warn-' + Math.random().toString(36).substring(2, 9),
          type: 'error',
          text: result.stderr,
          timestamp: Date.now(),
        },
      ]);
      return;
    }

    if (result.stdout === '__CLEAR__') {
      setLines([]);
      return;
    }

    const newOutputs: TerminalOutputLine[] = [cmdLine];

    if (result.stdout) {
      newOutputs.push({
        id: 'out-' + Math.random().toString(36).substring(2, 9),
        type: trimmed.startsWith('maple') ? 'maple' : 'output',
        text: result.stdout.trimEnd(),
        timestamp: Date.now(),
      });
    }

    if (result.stderr) {
      newOutputs.push({
        id: 'err-' + Math.random().toString(36).substring(2, 9),
        type: 'error',
        text: result.stderr.trimEnd(),
        timestamp: Date.now(),
      });
    }

    setLines((prev) => [...prev, ...newOutputs]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeCommand(inputVal);
      setInputVal('');
      setHistoryIndex(null);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (session.history.length === 0) return;
      const nextIndex =
        historyIndex === null
          ? session.history.length - 1
          : Math.max(0, historyIndex - 1);
      setHistoryIndex(nextIndex);
      setInputVal(session.history[nextIndex]?.command || '');
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex === null) return;
      const nextIndex = historyIndex + 1;
      if (nextIndex >= session.history.length) {
        setHistoryIndex(null);
        setInputVal('');
      } else {
        setHistoryIndex(nextIndex);
        setInputVal(session.history[nextIndex]?.command || '');
      }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      handleTabComplete();
    } else if (e.ctrlKey && e.key === 'l') {
      e.preventDefault();
      setLines([]);
    } else if (e.ctrlKey && e.key === 'c') {
      e.preventDefault();
      setLines((prev) => [
        ...prev,
        {
          id: 'cancel-' + Math.random().toString(36).substring(2, 9),
          type: 'command',
          text: inputVal + '^C',
          prompt: getPromptString(),
          timestamp: Date.now(),
        },
      ]);
      setInputVal('');
      setHistoryIndex(null);
    }
  };

  const handleTabComplete = () => {
    const raw = inputVal.trimStart();
    const parts = raw.split(/\s+/);
    if (parts.length <= 1) {
      const prefix = parts[0] || '';
      const match = BUILTIN_COMMANDS.find((cmd) => cmd.startsWith(prefix));
      if (match) {
        setInputVal(match + ' ');
      }
    } else {
      // Complete filename in current directory
      const lastPart = parts[parts.length - 1];
      try {
        const files = fs.listDirectory(session.cwd, false, false);
        const match = files.find((f) => f.startsWith(lastPart));
        if (match) {
          parts[parts.length - 1] = match;
          setInputVal(parts.join(' ') + (match.endsWith('/') ? '' : ' '));
        }
      } catch {
        // ignore
      }
    }
  };

  const confirmPending = () => {
    if (!pendingConfirm) return;
    const { command, action } = pendingConfirm;
    setPendingConfirm(null);

    const result = action();
    const cmdLine: TerminalOutputLine = {
      id: 'cmd-confirmed-' + Math.random().toString(36).substring(2, 9),
      type: 'command',
      text: `${command} [CONFIRMED BY USER]`,
      prompt: getPromptString(),
      timestamp: Date.now(),
    };

    const newOutputs: TerminalOutputLine[] = [cmdLine];
    if (result.stdout) {
      newOutputs.push({
        id: 'out-' + Math.random().toString(36).substring(2, 9),
        type: 'output',
        text: result.stdout.trimEnd(),
        timestamp: Date.now(),
      });
    }
    if (result.stderr) {
      newOutputs.push({
        id: 'err-' + Math.random().toString(36).substring(2, 9),
        type: 'error',
        text: result.stderr.trimEnd(),
        timestamp: Date.now(),
      });
    }
    setLines((prev) => [...prev, ...newOutputs]);
  };

  const cancelPending = () => {
    setPendingConfirm(null);
    setLines((prev) => [
      ...prev,
      {
        id: 'cancel-' + Math.random().toString(36).substring(2, 9),
        type: 'system',
        text: 'Operation cancelled by user.',
        timestamp: Date.now(),
      },
    ]);
  };

  const quickActions = [
    'help',
    'ls -a',
    'cat welcome.txt',
    'load maple',
    'maple inspect workspace',
    'sysinfo',
    'ps -a',
    'rm -rf /',
  ];

  return (
    <div
      className="flex flex-col flex-1 h-full bg-[#090d13] font-mono text-xs sm:text-sm text-neutral-200 overflow-hidden relative select-text"
      onClick={handleContainerClick}
    >
      {/* Terminal Output Area */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {lines.map((line) => {
          if (line.type === 'command') {
            return (
              <div key={line.id} className="flex flex-wrap items-start gap-2 pt-1 font-semibold">
                <span className="text-sky-400 select-none">{line.prompt}</span>
                <span className="text-neutral-100">{line.text}</span>
              </div>
            );
          }

          if (line.type === 'maple') {
            return (
              <div
                key={line.id}
                className="my-1.5 p-3 rounded-md bg-[#131722] border border-indigo-500/30 text-indigo-200 leading-relaxed whitespace-pre-wrap shadow-xs"
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 mb-1 select-none">
                  <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
                  MAPLE REASONING COPILOT
                </div>
                {line.text}
              </div>
            );
          }

          if (line.type === 'error') {
            return (
              <div
                key={line.id}
                className="text-rose-400 whitespace-pre-wrap leading-relaxed bg-rose-950/20 p-2 rounded border border-rose-900/30"
              >
                {line.text}
              </div>
            );
          }

          if (line.type === 'system') {
            return (
              <div key={line.id} className="text-neutral-400 whitespace-pre-wrap leading-relaxed">
                {line.text}
              </div>
            );
          }

          return (
            <div key={line.id} className="text-neutral-300 whitespace-pre-wrap leading-relaxed">
              {line.text}
            </div>
          );
        })}

        <div ref={bottomRef} />
      </div>

      {/* Confirmation Banner if dangerous command triggered */}
      {pendingConfirm && (
        <div className="mx-4 my-2 p-3.5 bg-amber-950/40 border border-amber-500/60 rounded-lg shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3 text-amber-200">
            <ShieldAlert className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
            <div>
              <div className="font-semibold text-amber-300 text-sm">
                Convexity Security Authorization
              </div>
              <div className="text-xs text-amber-200/90 mt-0.5">
                {pendingConfirm.reason}
              </div>
              <div className="text-[11px] font-mono text-neutral-400 mt-1">
                Command: <span className="text-amber-100 font-bold">{pendingConfirm.command}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              type="button"
              onClick={cancelPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirmPending}
              className="px-3 py-1.5 rounded text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-xs transition flex items-center gap-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Authorize & Run
            </button>
          </div>
        </div>
      )}

      {/* Input row */}
      <div className="px-4 py-2.5 bg-[#0d1117] border-t border-neutral-800/80 flex items-center gap-2">
        <span className="text-sky-400 font-semibold select-none shrink-0">
          {getPromptString()}
        </span>
        <input
          ref={inputRef}
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          spellCheck={false}
          autoComplete="off"
          className="flex-1 bg-transparent border-0 outline-none text-neutral-100 placeholder-neutral-600 font-mono text-xs sm:text-sm"
          placeholder="Type command ('help', 'load maple', 'cat welcome.txt')..."
        />
        <button
          type="button"
          onClick={() => {
            executeCommand(inputVal);
            setInputVal('');
            setHistoryIndex(null);
          }}
          className="p-1 text-neutral-400 hover:text-sky-400 transition"
          title="Run command"
        >
          <CornerDownLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Quick command buttons for smooth exploration */}
      <div className="px-4 py-1.5 bg-[#090d13] border-t border-neutral-800/50 flex items-center gap-1.5 overflow-x-auto text-[11px] text-neutral-400">
        <span className="text-neutral-500 uppercase font-semibold text-[10px] tracking-wider select-none shrink-0">
          Quick Run:
        </span>
        {quickActions.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => executeCommand(action)}
            className="px-2 py-0.5 rounded bg-neutral-800/60 hover:bg-neutral-800 text-neutral-300 hover:text-sky-300 border border-neutral-700/60 whitespace-nowrap transition"
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
};
