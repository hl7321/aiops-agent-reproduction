import type { PublicConfig } from "../build/public-config.mjs";

export const publicConfig: Readonly<PublicConfig> = Object.freeze({ ...__PUBLIC_CONFIG__ });
