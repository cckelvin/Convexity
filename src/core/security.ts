export interface SecurityCheckResult {
  dangerous: boolean;
  reason: string;
  requiresConfirmation: boolean;
  executable: string;
  args: string[];
}

export class ConvexitySecurity {
  private static DANGEROUS_COMMANDS = new Set([
    'format',
    'mkfs',
    'fdisk',
    'diskpart',
    'shutdown',
    'reboot',
    'poweroff',
    'dd',
  ]);

  public static analyze(commandStr: string, source: 'human' | 'maple' = 'human'): SecurityCheckResult {
    const trimmed = commandStr.trim();
    if (!trimmed) {
      return { dangerous: false, reason: '', requiresConfirmation: false, executable: '', args: [] };
    }

    // Split args respecting quotes
    const parts = trimmed.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [];
    const rawTokens = parts.map((p) => p.replace(/^["']|["']$/g, ''));
    const executable = (rawTokens[0] || '').toLowerCase();
    const args = rawTokens.slice(1);

    let dangerous = false;
    let reason = '';

    // Direct match against dangerous commands
    if (this.DANGEROUS_COMMANDS.has(executable)) {
      dangerous = true;
      reason = `Critical system operation detected: '${executable}'`;
    }

    // Check destructive file operations
    if (executable === 'rm' || executable === 'del') {
      const hasRecursive = args.some((arg) =>
        ['-r', '-rf', '-fr', '--recursive', '/s'].includes(arg.toLowerCase())
      );
      const targetsRootOrSys = args.some((arg) => ['/', '~', '*', '/home'].includes(arg));

      if (hasRecursive && targetsRootOrSys) {
        dangerous = true;
        reason = `Destructive recursive deletion of system or parent path (${args.join(' ')})`;
      } else if (hasRecursive) {
        dangerous = true;
        reason = `Recursive directory deletion '${args.join(' ')}'`;
      }
    }

    // Check device overwrites
    if (trimmed.includes('>') && (trimmed.includes('/dev/') || trimmed.includes('\\\\.\\'))) {
      dangerous = true;
      reason = 'Direct raw storage device overwrite detected';
    }

    // Check critical process termination
    if (executable === 'kill' && (args.includes('1') || args.includes('-9 1'))) {
      dangerous = true;
      reason = 'Attempted termination of root init process (PID 1)';
    }

    const requiresConfirmation = source === 'maple' ? dangerous : false;

    return {
      dangerous,
      reason,
      requiresConfirmation,
      executable,
      args,
    };
  }
}
