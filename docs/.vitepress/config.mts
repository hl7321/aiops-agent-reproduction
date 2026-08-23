import { defineConfig } from "vitepress";

import { openspecSidebar } from "./openspec-sidebar.generated.mts";

export default defineConfig({
  lang: "zh-CN",
  title: "智能 OnCall Agent",
  description: "OpenSpec 驱动的智能 OnCall Agent 项目 WIKI",
  // include 源文件不是独立路由；生成 change 目录已提供真实 proposal.md 包装页。
  ignoreDeadLinks: [/^\.\/proposal$/],
  themeConfig: {
    nav: [
      { text: "首页", link: "/" },
      { text: "OpenSpec 变更", link: "/changes/" },
      { text: "主规格", link: "/specs/" },
      { text: "运维", link: "/operations-and-monitoring" },
    ],
    sidebar: {
      "/changes/": openspecSidebar,
      "/specs/": openspecSidebar,
    },
    outline: { label: "本页目录" },
    docFooter: { prev: "上一页", next: "下一页" },
    search: { provider: "local" },
  },
});
