// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";

import { renderSafeMarkdown } from "./renderSafeMarkdown";

describe("renderSafeMarkdown", () => {
  it("渲染 Markdown 并把不可信 raw HTML 当作文本处理", () => {
    const html = renderSafeMarkdown("**安全** <img src=x onerror=alert(1)> <script>alert(2)</script>");
    expect(html).toContain("<strong>安全</strong>");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
    expect(html).toContain("&lt;img");
  });

  it("清除危险链接协议", () => {
    expect(renderSafeMarkdown("[危险](javascript:alert(1))")).not.toContain("javascript:");
  });
});
