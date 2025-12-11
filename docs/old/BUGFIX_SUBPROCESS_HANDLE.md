# Bugfix: Subprocess File Handle Management

## Date: Nov 27, 2025

## Issue
Deep research runs launched from the dashboard UI were getting stuck at "queued" status and never progressing.

## Root Cause
The API server was closing the stdout file handle immediately after spawning the subprocess:

```python
# BUGGY CODE
stdout_handle = stdout_path.open("w", encoding="utf-8")
subprocess.Popen(cmd, stdout=stdout_handle, stderr=stdout_handle, env=env)
stdout_handle.close()  # ❌ BUG: Closed while subprocess still needs it!
```

**What went wrong:**
1. Parent process opened file handle
2. Parent spawned subprocess and passed the handle
3. Parent immediately closed the handle
4. Subprocess tried to write to closed handle → failed silently
5. Subprocess likely crashed with no logs
6. Run stayed at "queued" forever

## The Fix

```python
# FIXED CODE
stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)  # Line buffered
subprocess.Popen(
    cmd,
    cwd=str(WORKSPACE_ROOT),
    stdout=stdout_handle,
    stderr=stdout_handle,
    env=env,
    start_new_session=True,  # Detach from parent session
    close_fds=False,  # Keep file descriptors open for subprocess
)
# Don't close handle - subprocess owns it and will close on exit
```

**Key changes:**
1. **Line buffering** (`buffering=1`) - Real-time log flushing
2. **`start_new_session=True`** - Subprocess runs independently
3. **`close_fds=False`** - File descriptors stay open for subprocess
4. **No `close()`** - Let subprocess own and close the handle

## Files Modified
- `servers/research_dashboard.py`
  - Fixed `create_run()` endpoint (line ~170)
  - Fixed `create_deep_research()` endpoint (line ~230)

## Testing
1. API server restarted with fix
2. File handles now properly managed
3. Subprocess logs work correctly
4. Runs progress as expected

## Prevention
This is a common Python subprocess pitfall. Best practices:
1. Never close file handles passed to subprocesses
2. Use `start_new_session=True` for background processes
3. Enable buffering for real-time logs
4. Test subprocess launches in development

## Impact
- **Before:** All dashboard-launched runs failed silently
- **After:** Runs work correctly, logs stream properly
- **Affected runs:** Any queued runs need to be relaunched

## Rollout
- [x] Fix implemented
- [x] API server restarted
- [x] Testing confirmed working
- [ ] User needs to refresh dashboard and relaunch runs






