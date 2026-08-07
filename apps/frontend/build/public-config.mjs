// @ts-check

import { readFile } from "node:fs/promises";

/** @typedef {{ readonly title: string, readonly apiBaseUrl: string, readonly analyticsPublicKey: string }} PublicConfig */

/**
 * 递归合并 JSON object；数组和标量由 override 整体替换。
 * @param {Record<string, unknown>} base
 * @param {Record<string, unknown>} override
 * @returns {Record<string, unknown>}
 */
export function deepMerge(base, override) {
  /** @type {Record<string, unknown>} */
  const merged = structuredClone(base);
  for (const [key, overrideValue] of Object.entries(override)) {
    const baseValue = merged[key];
    merged[key] = isJsonObject(baseValue) && isJsonObject(overrideValue)
      ? deepMerge(baseValue, overrideValue)
      : structuredClone(overrideValue);
  }
  return merged;
}

/**
 * 读取显式文件路径并合并项目配置与用户配置。
 * @param {string} projectPath
 * @param {string} userPath
 * @returns {Promise<Record<string, unknown>>}
 */
export async function loadMergedConfig(projectPath, userPath) {
  const [projectText, userText] = await Promise.all([
    readFile(projectPath, "utf8"),
    readFile(userPath, "utf8"),
  ]);
  return deepMerge(parseJsonObject(projectText, projectPath), parseJsonObject(userText, userPath));
}

/**
 * 将完整配置投影为浏览器允许公开的字段。
 * @param {Record<string, unknown>} config
 * @returns {PublicConfig}
 */
export function toPublicConfig(config) {
  const frontend = asJsonObject(config.frontend);
  const analytics = asJsonObject(config.analytics);
  return Object.freeze({
    title: asString(frontend.title, "智能 OnCall Agent"),
    apiBaseUrl: asString(frontend.apiBaseUrl, "http://127.0.0.1:8000"),
    analyticsPublicKey: asString(analytics.publicKey, ""),
  });
}

/** @param {string} text @param {string} source @returns {Record<string, unknown>} */
function parseJsonObject(text, source) {
  /** @type {unknown} */
  const raw = JSON.parse(text);
  const normalized = normalizeJson(raw);
  if (!isJsonObject(normalized)) {
    throw new TypeError(`配置文件顶层必须是 JSON object: ${source}`);
  }
  return normalized;
}

/** @param {unknown} value @returns {unknown} */
function normalizeJson(value) {
  if (
    value === null
    || typeof value === "boolean"
    || typeof value === "number"
    || typeof value === "string"
  ) {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => normalizeJson(item));
  }
  if (typeof value === "object") {
    /** @type {Record<string, unknown>} */
    const normalized = {};
    for (const [key, item] of Object.entries(value)) {
      normalized[key] = normalizeJson(item);
    }
    return normalized;
  }
  throw new TypeError(`不支持的 JSON 值类型: ${typeof value}`);
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isJsonObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** @param {unknown} value @returns {Record<string, unknown>} */
function asJsonObject(value) {
  return isJsonObject(value) ? value : {};
}

/** @param {unknown} value @param {string} fallback @returns {string} */
function asString(value, fallback) {
  return typeof value === "string" ? value : fallback;
}
