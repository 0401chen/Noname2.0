const viteEnv = (
  import.meta as ImportMeta & {
    env?: Record<string, string | undefined>;
  }
).env;

export const AGENT_NAME = viteEnv?.VITE_AGENT_NAME?.trim() || "Noname助手";

const LEGACY_AGENT_NAMES = ["重启键"];
const BRAND_ATTRIBUTES = ["title", "aria-label", "alt", "placeholder"] as const;

function replaceLegacyName(value: string): string {
  return LEGACY_AGENT_NAMES.reduce(
    (current, legacyName) => current.replaceAll(legacyName, AGENT_NAME),
    value,
  );
}

function replaceTextNode(node: Text): void {
  const nextValue = replaceLegacyName(node.data);
  if (nextValue !== node.data) node.data = nextValue;
}

function applyBranding(root: Node): void {
  if (root instanceof Text) {
    replaceTextNode(root);
    return;
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    if (walker.currentNode instanceof Text) {
      replaceTextNode(walker.currentNode);
    }
  }

  if (!(root instanceof Element)) return;

  const elements = [root, ...root.querySelectorAll<HTMLElement>("*")];
  for (const element of elements) {
    for (const attribute of BRAND_ATTRIBUTES) {
      const currentValue = element.getAttribute(attribute);
      if (!currentValue) continue;
      const nextValue = replaceLegacyName(currentValue);
      if (nextValue !== currentValue) element.setAttribute(attribute, nextValue);
    }
  }
}

export function installBranding(): void {
  document.title = `${AGENT_NAME} · Re:Play`;
  applyBranding(document.documentElement);

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "characterData" && mutation.target instanceof Text) {
        replaceTextNode(mutation.target);
        continue;
      }

      if (mutation.type === "attributes" && mutation.target instanceof Element) {
        applyBranding(mutation.target);
        continue;
      }

      for (const node of mutation.addedNodes) applyBranding(node);
    }
  });

  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [...BRAND_ATTRIBUTES],
  });
}
