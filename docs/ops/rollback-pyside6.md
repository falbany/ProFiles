# PySide6 Rollback Procedure

## If Phase 6 fails (default backend = qt breaks)

1. **Immediate rollback:**
   ```bash
   git revert <phase-6-commit-hash>
   git push origin main
   ```

2. **OR environment override:**
   ```bash
   export PROFILES_GUI_BACKEND=tk
   ```

3. **Verify:**
   ```bash
   pytest tests/  # Should pass with Tk backend
   ```
