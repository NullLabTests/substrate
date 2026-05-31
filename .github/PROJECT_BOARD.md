# Project Board Setup

The Substrate Development board tracks all work across milestones.

## Columns

| Column | Cards | Automation |
|--------|-------|------------|
| Backlog | All unstarted issues | New issues auto-added |
| M1 - Foundation | #1, #2, #3, #4 | When milestone=M1 |
| M2 - Persistent Agents | #5, #6, #7 | When milestone=M2 |
| M3 - Social Systems | #8, #9, #10, #11 | When milestone=M3 |
| M4 - Evolution | #12, #13, #14 | When milestone=M4 |
| M5 - Observatory | #15, #16 | When milestone=M5 |
| M6 - Long-Horizon Experiments | #17, #18, #19 | When milestone=M6 |
| In Progress | Actively being worked on | When PR opened |
| Review | PR awaiting review | When PR marked ready |
| Done | Merged/completed | When PR merged/issue closed |

## Setup

```bash
# Requires token with project scope
gh auth refresh -s project,read:project

# Create board
gh project create --owner NullLabTests --title "Substrate Development"

# Add columns (via web UI or API)
# Configure automation rules in board settings
```
