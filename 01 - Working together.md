# Working together in this workspace

Your whole team shares these files. Each of you has your own copy of a notebook open in
your browser, and edits are not shared live, so two people editing the same notebook
overwrite each other.

- **One person edits a notebook at a time.** Agree who is working in which notebook.
- **Better still, each person works in their own notebook,** for example
  `analysis-sam.ipynb`, and you combine the work in a final notebook in `Submission`.
- **Before you edit a notebook a teammate used,** close it and open it again, so you start
  from their latest saved version.

## "File Changed"

If Jupyter says a notebook "has changed on disk since the last time it was opened or saved",
a teammate saved it after you opened it.

- **Revert** loads their saved version. Your unsaved changes are lost.
- **Overwrite** saves your version over theirs. Their changes are lost.
- **Cancel** decides nothing yet; Jupyter asks again when you next save.

If you both have changes to keep: choose **Cancel**, copy your cells into a new notebook,
then reopen the original (or choose **Revert**) and add them back.
