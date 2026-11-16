import { defineConfig } from "vite";
import fs from "node:fs/promises";
import path from "node:path";
async function linkTree(src, dest) {
  await fs.mkdir(dest, { recursive: true });
  for (const e of await fs.readdir(src, { withFileTypes: true })) {
    const a = path.join(src, e.name),
      b = path.join(dest, e.name);
    if (e.isDirectory()) await linkTree(a, b);
    else {
      try {
        await fs.link(a, b);
      } catch {
        await fs.copyFile(a, b);
      }
    }
  }
}
export default defineConfig(({ command }) => ({
  publicDir: command === "build" ? false : "public",
  plugins: [
    {
      name: "publish-public-assets",
      apply: "build",
      async closeBundle() {
        const root = process.cwd();
        for (const entry of await fs.readdir(path.join(root, "public"), {
          withFileTypes: true,
        })) {
          const a = path.join(root, "public", entry.name),
            b = path.join(root, "dist", entry.name);
          if (entry.name === "national") await linkTree(a, b);
          else await fs.cp(a, b, { recursive: true });
        }
      },
    },
  ],
}));
