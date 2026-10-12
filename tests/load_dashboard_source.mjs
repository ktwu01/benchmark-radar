import { readFileSync } from "node:fs";

export function loadDashboardSource() {
  const assets = new URL("../site/assets/", import.meta.url);
  const glyphs = readFileSync(new URL("glyphs.js", assets), "utf8").replace(
    /^export \{[\s\S]*?\};$/m,
    "",
  );
  const fields = readFileSync(new URL("fields.js", assets), "utf8").replace(/^export /gm, "");
  const skyline = readFileSync(new URL("skyline.js", assets), "utf8").replace(/^export /gm, "");
  const app = readFileSync(new URL("app.js", assets), "utf8")
    .replace(/^import \{[\s\S]*?\} from "\.\/glyphs\.js";$/m, "")
    .replace(/^import \{[^\n]*\} from "\.\/fields\.js";$/m, "")
    .replace(/^import \{[^\n]*\} from "\.\/skyline\.js";$/m, "");
  return fields + "\nconst researchFields = fields;\n" + skyline + glyphs + app;
}
