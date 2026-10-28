// All useful-action prompts share one budget, including standalone benchmark
// pages. Keep the key from #1027 so earlier readers are not asked again.
const STAR_PROMPT_KEY = "benchmark-radar:star-prompt:v1";
const CARD_COPY = [
  "If this saved you research time, give Benchmark Radar a star.",
  "如果它帮你省了查资料的时间，给 Benchmark Radar 点个 Star 吧。",
];
const STAR_PROMPT_COPY = {
  subscribe: [
    "Thanks for subscribing. A GitHub star helps other eval builders find Benchmark Radar.",
    "感谢订阅。在 GitHub 上点个 Star，能让更多做评测的人找到 Benchmark Radar。",
  ],
  cite: [
    "Thanks for citing. A GitHub star helps other eval builders find Benchmark Radar.",
    "感谢引用。在 GitHub 上点个 Star，能让更多做评测的人找到 Benchmark Radar。",
  ],
  save: [
    "Saved benchmarks stay in this browser. Star the repository to find Benchmark Radar again anywhere.",
    "收藏的 benchmark 只保存在这个浏览器里。给仓库点个 Star，换台设备也能找回 Benchmark Radar。",
  ],
  card_copy_image: CARD_COPY,
  card_copy_link: CARD_COPY,
  card_download: CARD_COPY,
};
let starPromptShown = false;

function trackStarPrompt(name) {
  // The consent loader creates Clarity only for readers who opted in.
  window.clarity?.("event", name);
}

export function starPrompt(trigger, onClose) {
  if (!STAR_PROMPT_COPY[trigger] || starPromptShown) return null;
  starPromptShown = true;
  try {
    if (window.localStorage.getItem(STAR_PROMPT_KEY)) return null;
    window.localStorage.setItem(STAR_PROMPT_KEY, trigger);
  } catch {
    // With blocked storage, the module still limits prompts to once per page.
  }
  const zh = document.documentElement.lang.startsWith("zh");
  const prompt = document.createElement("p");
  prompt.className = "star-prompt";
  prompt.setAttribute("role", "status");
  const close = () => {
    prompt.remove();
    onClose?.();
  };
  const copy = document.createElement("span");
  copy.textContent = STAR_PROMPT_COPY[trigger][zh ? 1 : 0];
  const link = document.createElement("a");
  link.className = "star-prompt-link";
  link.textContent = zh ? "★ 在 GitHub 上点 Star" : "★ Star on GitHub";
  link.setAttribute("href", "https://github.com/ktwu01/benchmark-radar");
  link.setAttribute("target", "_blank");
  // Retain referrer attribution without exposing the opener to the new tab.
  link.setAttribute("rel", "noopener");
  link.addEventListener("click", () => {
    trackStarPrompt(`star_prompt_click_${trigger}`);
    close();
  });
  const dismiss = document.createElement("button");
  dismiss.className = "star-prompt-dismiss";
  dismiss.textContent = "×";
  dismiss.setAttribute("type", "button");
  dismiss.setAttribute("aria-label", zh ? "关闭" : "Close");
  dismiss.setAttribute("title", zh ? "关闭" : "Close");
  dismiss.addEventListener("click", close);
  prompt.append(copy, link, dismiss);
  trackStarPrompt(`star_prompt_shown_${trigger}`);
  return prompt;
}
