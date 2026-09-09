import React from 'react';
import { X, BookOpen, Terminal, Shield, Sparkles } from 'lucide-react';

interface HelpModalProps {
  onClose: () => void;
  onRunCommand: (cmd: string) => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ onClose, onRunCommand }) => {
  const sections = [
    {
      title: 'File & Directory Commands',
      icon: Terminal,
      color: 'text-sky-400',
      commands: [
        { cmd: 'pwd', desc: 'Print current working directory' },
        { cmd: 'cd <path>', desc: 'Change directory (~ for home)' },
        { cmd: 'ls [-a] [-r]', desc: 'List files and directories' },
        { cmd: 'cat <file>', desc: 'Output file contents' },
        { cmd: 'write <file> <text>', desc: 'Write contents to file' },
        { cmd: 'append <file> <text>', desc: 'Append line to file' },
        { cmd: 'touch <file>', desc: 'Create empty file or update timestamp' },
        { cmd: 'mkdir <path>', desc: 'Create new directory' },
        { cmd: 'rm [-r] <path>', desc: 'Remove file or directory' },
        { cmd: 'stat <file>', desc: 'Show size, permissions, and timestamps' },
      ],
    },
    {
      title: 'Environment & Process',
      icon: Shield,
      color: 'text-emerald-400',
      commands: [
        { cmd: 'env', desc: 'Display all environment variables' },
        { cmd: 'set <key> <val>', desc: 'Set or update an environment variable' },
        { cmd: 'unset <key>', desc: 'Remove an environment variable' },
        { cmd: 'alias <name> <cmd>', desc: 'Create a command shortcut alias' },
        { cmd: 'jobs / ps [-a]', desc: 'List background processes & status' },
        { cmd: 'run <command>', desc: 'Start background process' },
        { cmd: 'kill [-9] <pid>', desc: 'Terminate process by PID' },
        { cmd: 'sysinfo', desc: 'Print virtual system telemetry' },
      ],
    },
    {
      title: 'Maple AI & Utilities',
      icon: Sparkles,
      color: 'text-indigo-400',
      commands: [
        { cmd: 'load maple', desc: 'Activate Maple AI copilot & safety guardrails' },
        { cmd: 'kill maple', desc: 'Unload Maple copilot' },
        { cmd: 'maple <prompt>', desc: 'Direct question or task to Maple' },
        { cmd: 'tools / libraries', desc: 'Inspect registered extensions and tools' },
        { cmd: 'clear', desc: 'Clear the terminal output (Ctrl+L)' },
        { cmd: 'history', desc: 'Display recent commands' },
      ],
    },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-neutral-800 rounded-xl w-full max-w-3xl flex flex-col shadow-2xl overflow-hidden font-mono text-xs sm:text-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 bg-[#0d1117]">
          <div className="flex items-center gap-2 text-neutral-200 font-semibold">
            <BookOpen className="w-4 h-4 text-sky-400" />
            <span>Convexity Terminal Manual & Reference</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-5 overflow-y-auto max-h-[70vh]">
          {sections.map((sec) => {
            const Icon = sec.icon;
            return (
              <div key={sec.title} className="space-y-2">
                <div className="flex items-center gap-2 text-neutral-200 font-semibold text-xs border-b border-neutral-800 pb-1">
                  <Icon className={`w-3.5 h-3.5 ${sec.color}`} />
                  <span>{sec.title}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {sec.commands.map((c) => (
                    <div
                      key={c.cmd}
                      className="p-2 rounded bg-neutral-900/60 border border-neutral-800/80 flex items-start justify-between gap-2 hover:border-neutral-700 transition"
                    >
                      <div>
                        <code className="text-sky-300 font-bold text-xs">{c.cmd}</code>
                        <div className="text-[11px] text-neutral-400 mt-0.5">{c.desc}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          onRunCommand(c.cmd.split(' ')[0]);
                          onClose();
                        }}
                        className="px-1.5 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 text-[10px] shrink-0"
                      >
                        Try
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          <div className="p-3 bg-indigo-950/20 border border-indigo-800/40 rounded-lg text-indigo-300 text-xs">
            <span className="font-semibold text-indigo-200">Pro Tip: </span>
            Use the <kbd className="px-1 py-0.5 rounded bg-neutral-800 text-neutral-200 text-[10px]">Tab</kbd> key for command and filename completion, and <kbd className="px-1 py-0.5 rounded bg-neutral-800 text-neutral-200 text-[10px]">Up / Down</kbd> arrow keys to navigate command history.
          </div>
        </div>
      </div>
    </div>
  );
};
