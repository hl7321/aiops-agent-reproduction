import DOMPurify from "dompurify";
import { marked } from "marked";

const renderer = new marked.Renderer();
renderer.html = ({ text }) => escapeHtml(text);
renderer.link = ({ href, title, tokens }) => {
  const text = renderer.parser.parseInline(tokens);
  if (!isSafeLink(href)) return text;
  const titleAttribute = title == null ? "" : ` title="${escapeHtml(title)}"`;
  return `<a href="${escapeHtml(href)}"${titleAttribute}>${text}</a>`;
};

export function renderSafeMarkdown(source: string): string {
  const rendered = marked.parse(source, {
    async: false,
    breaks: true,
    gfm: true,
    renderer,
  });
  return DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: [
      "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4",
      "h5", "h6", "hr", "li", "ol", "p", "pre", "strong", "table", "tbody",
      "td", "th", "thead", "tr", "ul",
    ],
    ALLOWED_ATTR: ["href", "title"],
  });
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function isSafeLink(value: string): boolean {
  if (value.startsWith("/") || value.startsWith("#")) return true;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" || parsed.protocol === "mailto:";
  } catch {
    return false;
  }
}
