export interface FileNode {
  name: string;
  type: 'file';
  content: string;
  size: number;
  modified: number;
  permissions?: string;
  hidden?: boolean;
}

export interface DirectoryNode {
  name: string;
  type: 'dir';
  children: Record<string, FSNode>;
  modified: number;
  permissions?: string;
  hidden?: boolean;
}

export type FSNode = FileNode | DirectoryNode;

export interface FileStat {
  path: string;
  name: string;
  type: 'file' | 'directory';
  size: number;
  modified: string;
  permissions: string;
  hidden: boolean;
}

export interface ProcessItem {
  pid: number;
  command: string;
  state: 'running' | 'finished' | 'stopped' | 'killed';
  startedAt: number;
  source: 'human' | 'maple' | 'system';
}

export interface HistoryItem {
  id: string;
  command: string;
  timestamp: number;
  exitCode?: number;
  duration?: number;
  source: 'human' | 'maple' | 'system';
}

export interface TerminalSession {
  sessionId: string;
  name: string;
  cwd: string;
  environment: Record<string, string>;
  aliases: Record<string, string>;
  history: HistoryItem[];
  mapleLoaded: boolean;
  mapleSessionId?: string;
  activeJobs: number[];
  columns: number;
  rows: number;
  createdAt: number;
}

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  handled: boolean;
  requiresConfirmation?: boolean;
  confirmationReason?: string;
  pendingAction?: () => CommandResult;
}

export interface MapleThought {
  id: string;
  timestamp: number;
  type: 'analysis' | 'warning' | 'suggestion' | 'action';
  message: string;
  relatedCommand?: string;
}

export interface TerminalOutputLine {
  id: string;
  type: 'command' | 'output' | 'error' | 'system' | 'maple';
  text: string;
  prompt?: string;
  timestamp: number;
}
