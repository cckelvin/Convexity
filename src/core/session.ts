import { TerminalSession, HistoryItem } from '../types';

export class SessionManager {
  private sessions: Map<string, TerminalSession> = new Map();
  private activeSessionId: string;

  constructor() {
    const defaultSession: TerminalSession = {
      sessionId: 'sess-' + Math.random().toString(36).substring(2, 9),
      name: 'Default Session',
      cwd: '/home/user',
      environment: {
        USER: 'user',
        HOME: '/home/user',
        SHELL: '/bin/convexity',
        TERM: 'xterm-256color',
        CONVEXITY_VERSION: '1.2.0',
        MAPLE_STATUS: 'inactive',
      },
      aliases: {
        ll: 'ls -a',
        la: 'ls -a',
        cls: 'clear',
      },
      history: [],
      mapleLoaded: false,
      activeJobs: [],
      columns: 120,
      rows: 30,
      createdAt: Date.now(),
    };

    this.sessions.set(defaultSession.sessionId, defaultSession);
    this.activeSessionId = defaultSession.sessionId;
  }

  public getActiveSession(): TerminalSession {
    return this.sessions.get(this.activeSessionId)!;
  }

  public getSession(id: string): TerminalSession | undefined {
    return this.sessions.get(id);
  }

  public listSessions(): TerminalSession[] {
    return Array.from(this.sessions.values());
  }

  public createSession(name?: string): TerminalSession {
    const count = this.sessions.size + 1;
    const session: TerminalSession = {
      sessionId: 'sess-' + Math.random().toString(36).substring(2, 9),
      name: name || `Session ${count}`,
      cwd: '/home/user',
      environment: {
        USER: 'user',
        HOME: '/home/user',
        SHELL: '/bin/convexity',
        TERM: 'xterm-256color',
        CONVEXITY_VERSION: '1.2.0',
        MAPLE_STATUS: 'inactive',
      },
      aliases: {
        ll: 'ls -a',
        cls: 'clear',
      },
      history: [],
      mapleLoaded: false,
      activeJobs: [],
      columns: 120,
      rows: 30,
      createdAt: Date.now(),
    };
    this.sessions.set(session.sessionId, session);
    this.activeSessionId = session.sessionId;
    return session;
  }

  public switchSession(id: string): boolean {
    if (this.sessions.has(id)) {
      this.activeSessionId = id;
      return true;
    }
    return false;
  }

  public removeSession(id: string): boolean {
    if (this.sessions.size <= 1) return false;
    const deleted = this.sessions.delete(id);
    if (this.activeSessionId === id) {
      this.activeSessionId = Array.from(this.sessions.keys())[0];
    }
    return deleted;
  }

  public addHistory(sessionId: string, command: string, exitCode?: number, duration?: number): HistoryItem {
    const session = this.sessions.get(sessionId);
    if (!session) throw new Error('Session not found');

    const item: HistoryItem = {
      id: Math.random().toString(36).substring(2, 9),
      command,
      timestamp: Date.now(),
      exitCode,
      duration,
      source: session.mapleLoaded ? 'maple' : 'human',
    };

    session.history.push(item);
    if (session.history.length > 500) {
      session.history.shift();
    }
    return item;
  }

  public setCwd(sessionId: string, cwd: string): void {
    const session = this.sessions.get(sessionId);
    if (session) session.cwd = cwd;
  }

  public setEnv(sessionId: string, key: string, val: string): void {
    const session = this.sessions.get(sessionId);
    if (session) session.environment[key] = val;
  }

  public unsetEnv(sessionId: string, key: string): void {
    const session = this.sessions.get(sessionId);
    if (session) delete session.environment[key];
  }

  public setAlias(sessionId: string, key: string, val: string): void {
    const session = this.sessions.get(sessionId);
    if (session) session.aliases[key] = val;
  }

  public removeAlias(sessionId: string, key: string): boolean {
    const session = this.sessions.get(sessionId);
    if (session && key in session.aliases) {
      delete session.aliases[key];
      return true;
    }
    return false;
  }

  public setMapleLoaded(sessionId: string, loaded: boolean): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.mapleLoaded = loaded;
      session.environment['MAPLE_STATUS'] = loaded ? 'active' : 'inactive';
      if (loaded && !session.mapleSessionId) {
        session.mapleSessionId = 'maple-' + Math.random().toString(36).substring(2, 8);
      }
    }
  }
}
