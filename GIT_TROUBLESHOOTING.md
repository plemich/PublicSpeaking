# Git Troubleshooting Guide

## Fixed: Git index.lock Error

### Problem
You encountered the error:
```
fatal: Unable to create '/path/to/repo/.git/index.lock': File exists.
```

### Root Cause
This error occurs when:
1. A Git process was interrupted or crashed, leaving a stale lock file
2. Multiple Git processes try to modify the index simultaneously
3. In this repository's case: improper `.gitignore` configuration allowed system files to be tracked, causing conflicts

### Solution Applied
1. **Renamed `Gitignore` → `.gitignore`**: Git only recognizes `.gitignore` (with a dot prefix)
2. **Removed tracked `.DS_Store` files**: These macOS system files were causing conflicts
3. **Enhanced `.gitignore`**: Added patterns to prevent future issues with:
   - macOS system files (`.DS_Store`)
   - Git lock files (`*.lock`, `.git/index.lock`)
   - Editor temporary files

### If You Encounter index.lock Error Again

**Quick Fix:**
```bash
# Remove the lock file manually
rm -f .git/index.lock

# Then retry your Git command
git status
```

**Important Notes:**
- Only remove `index.lock` if you're sure no other Git process is running
- Check for running Git processes: `ps aux | grep git`
- If the issue persists, it may indicate a deeper problem with your Git repository

### Prevention
- The new `.gitignore` configuration should prevent most causes of this error
- Always ensure Git operations complete successfully before starting new ones
- Avoid force-quitting terminal windows during Git operations

### Additional Resources
- [Git Documentation: gitignore](https://git-scm.com/docs/gitignore)
- [GitHub: Working with .gitignore](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files)
