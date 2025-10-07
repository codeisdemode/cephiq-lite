# GitHub Workflow for Beginners

## Quick Start Commands

### 1. Check Current Status
```bash
git status
```
Shows what files are changed, staged, or untracked.

### 2. Add Files to Track Changes
```bash
# Add specific file
git add filename.py

# Add all changes in current directory
git add .

# Add specific file type
git add *.py
```

### 3. Commit Changes with Message
```bash
git commit -m "Description of what you changed"
```

### 4. Push to GitHub
```bash
git push origin main
```

## Daily Workflow

### When You Start Working
1. **Pull latest changes** (if working with others):
   ```bash
   git pull origin main
   ```

### When You Make Changes
1. **Check what you changed**:
   ```bash
   git status
   ```

2. **Add files you want to save**:
   ```bash
   git add filename.py
   # OR
   git add .
   ```

3. **Commit with clear message**:
   ```bash
   git commit -m "feat: Add new feature"
   git commit -m "fix: Fix bug in agent.py"
   git commit -m "docs: Update README"
   ```

4. **Push to GitHub**:
   ```bash
   git push origin main
   ```

## Useful Git Commands

### View History
```bash
# See recent commits
git log --oneline -10

# See what changed in a file
git diff filename.py
```

### Undo Changes
```bash
# Undo changes to a file (before adding)
git restore filename.py

# Remove file from staging (after git add)
git restore --staged filename.py

# Undo last commit (be careful!)
git reset --soft HEAD~1
```

### Branching (Advanced)
```bash
# Create new branch
git checkout -b feature/new-feature

# Switch back to main
git checkout main

# Merge branch
git merge feature/new-feature
```

## Good Commit Message Examples

- `feat: Add multi-tool execution in envelope engine`
- `fix: Resolve issue with tool validation`
- `docs: Update architecture documentation`
- `refactor: Clean up agent loop code`
- `test: Add tests for envelope validation`

## What NOT to Commit

- API keys or secrets
- Large files (PDFs, videos)
- Temporary files
- IDE configuration
- Log files

## Quick Reference Card

```
Daily Workflow:
1. git status          # See what changed
2. git add .           # Add all changes
3. git commit -m "msg" # Save changes
4. git push            # Upload to GitHub

Check History:
git log --oneline      # See recent commits
git diff filename.py   # See file changes

Undo Mistakes:
git restore file.py    # Undo file changes
git reset --soft HEAD~1 # Undo last commit
```

## Common Issues

### "Your branch is ahead of origin/main"
Just means you need to push:
```bash
git push origin main
```

### "Please commit your changes"
You have unsaved changes:
```bash
git add .
git commit -m "Your message"
git push origin main
```

### "Permission denied"
Make sure you're logged into GitHub on your computer.

## Next Steps

1. **Install GitHub Desktop** for visual interface
2. **Set up SSH keys** for easier authentication
3. **Learn about branches** for working on features
4. **Explore pull requests** for code review

Remember: Git is like "Save Game" for your code. Commit often, push regularly!