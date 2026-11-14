# Submitting your work

When your team lead submits on Keeboh, Keeboh keeps a copy of your team's workspace as your
final record, and your team's notebooks close. You don't need to move anything: Keeboh
looks at the whole workspace.

## What's in the record

- **All your source code and notebooks,** with their saved outputs, wherever they are in
  the workspace.
- **Your other files,** up to the hackathon's size limit, smallest first. Files over the
  per-file limit are left out, and so are the biggest files if the total is over the limit.
- **Your answers** to the questions on the submission page.

## What's left out

- **Key and password files:** `.env` files, and files ending in `.key` or `.pem` (and other
  key files, such as SSH keys). Keep your API keys in a `.env` file, never typed into a
  notebook or source file: those are copied.
- **Your team's Python environment** (the hidden `.keeboh` folder) and temporary files
  (checkpoints, caches, deleted files, Git history).
- **Links,** which are never followed.

The submission page lists exactly what will be copied and what will be left out before the
lead submits, and the receipt lists every file kept.

## Before the lead submits

- **Save every open notebook.** Keeboh copies what is saved, with its outputs.
- **Stop anything still running** (a training run, for example). Running kernels are shut
  down when the lead submits.
- **Check the list on the submission page.** Delete or move anything you don't want kept.

After the lead submits, the organizers and judges can still open your workspace.
