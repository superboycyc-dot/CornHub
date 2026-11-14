# Your team's workspace

This is your team's workspace. Everyone on the team sees the same files. When your team
lead submits, the team's access ends; the organizers and judges can still open it (see
**02 - Submitting your work**).

## What's here

- **01 - Working together:** how to share notebooks without overwriting each other.
- **02 - Submitting your work:** what happens when your team lead submits, and what the
  record keeps.
- **03 - Read me:** this file.
- **04 - GPU check:** run it to see your team's GPU.
- **05 - Nemotron on NVIDIA:** calls an NVIDIA Nemotron model with your team's NVIDIA Brev
  credits.
- **The challenge's starter kit,** as the organizers sent it: **`README.md` (start here)**,
  `01_Challenge` (the challenge statement), `02_QuickStats`, `03_Geospatial_References`,
  `04_Evaluation` (the evaluation data) and `Prior_Work` (papers).

Add your own notebooks and folders anywhere here. You can edit or delete these guides too;
Keeboh puts back only what's missing. The starter kit is added once: it's yours to change,
and a kit you delete isn't put back. It goes into your submission like everything else, so
delete the parts you don't use.

If your workspace has a `nass-hackathon-ucdavis-main` folder, it's from before 2026-11-10,
when the kit came in its own folder. Keeboh removed the files there that nobody had changed;
what's left in it is your team's.

The kit's instructions use PowerShell. To follow them, type `pwsh` in a terminal first, and
write paths with `/` instead of `\`, for example
`python ./02_QuickStats/download_corn_acres.py`. Setting the key with
`$env:NASS_API_KEY = "..."` works as written, and lasts only for that terminal.

## Data

The challenge's data is in the starter kit: `02_QuickStats` and `04_Evaluation`, with public
sources listed in `03_Geospatial_References`. You can use any other public data too: download
it into this workspace. The workspace holds 10 GB for the whole team, so keep large
downloads to what you need.

## Saving and the GPU

- **Save often.** What's saved here is kept when the GPU stops and starts again. Unsaved
  changes and anything held in a running notebook's memory are not.
- **The organizers start and stop your team's GPU.** It also stops after a while with
  nothing running. Opening the workspace never starts it.

## Installing packages

`pip install` in a terminal, or `%pip install` in a notebook, installs into your team's own
Python environment. It's kept in the hidden `.keeboh` folder in this workspace, so your
packages are still there after the GPU restarts. Don't delete that folder.

## Your submission

When your team lead submits, Keeboh keeps a copy of the whole workspace as your team's
record. **All your source code and notebooks go in.** `.env` files and files ending in
`.key` or `.pem` (and other key files) are **left out**, and so are your Python environment,
temporary files and the biggest files. `02 - Submitting your work` has the details.

## Keys and passwords

Everyone on your team can read every file here. Keep API keys and passwords in a `.env`
file, which stays out of your submission. Never type them into a notebook or source file:
those are submitted.

## Help

Ask the event's technical support team.
