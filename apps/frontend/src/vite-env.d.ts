/// <reference types="vite/client" />

import type { PublicConfig } from "../build/public-config.mjs";

declare global {
  const __PUBLIC_CONFIG__: PublicConfig;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>;
  export default component;
}
