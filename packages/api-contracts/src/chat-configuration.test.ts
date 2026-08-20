import { describe, expect, expectTypeOf, it } from "vitest";

import {
  CHAT_CONFIGURATION_OPENAPI_OPERATIONS,
  CHAT_SKILL_UPLOAD_POLICY,
} from "./openapi";
import type {
  ChatAssetDeleteData,
  ChatConfigurationData,
  ChatPrompt,
  ChatSkill,
  CreateChatPromptRequest,
  UpdateChatConfigurationRequest,
  UpdateChatPromptRequest,
} from "./chat-configuration";

describe("Chat Prompt 与 Skill 共享合同", () => {
  it("定义资产、选择与删除 DTO", () => {
    expectTypeOf<ChatPrompt>().toHaveProperty("content");
    expectTypeOf<ChatSkill>().toHaveProperty("summary");
    expectTypeOf<ChatConfigurationData>().toHaveProperty("selectedSkillIds");
    expectTypeOf<CreateChatPromptRequest>().toEqualTypeOf<{
      readonly label: string;
      readonly content: string;
    }>();
    expectTypeOf<UpdateChatPromptRequest>().toEqualTypeOf<CreateChatPromptRequest>();
    expectTypeOf<UpdateChatConfigurationRequest>().toEqualTypeOf<{
      readonly selectedPromptId: string | null;
      readonly selectedSkillIds: readonly string[];
    }>();
    expectTypeOf<ChatAssetDeleteData>().toHaveProperty("deleted");
  });

  it("公开严格 multipart policy", () => {
    expect(CHAT_SKILL_UPLOAD_POLICY).toEqual({
      multipart: { file: "file" },
      filename: "SKILL.md",
      maxBytes: 262144,
      maxNameCharacters: 64,
      maxDescriptionCharacters: 500,
      maxSummaryCharacters: 240,
      normalizedNamePattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$",
    });
  });

  it("登记七个 bearer OpenAPI operation", () => {
    expect(CHAT_CONFIGURATION_OPENAPI_OPERATIONS.map((item) => item.operationId)).toEqual([
      "getChatConfiguration",
      "updateChatConfiguration",
      "createChatPrompt",
      "updateChatPrompt",
      "deleteChatPrompt",
      "uploadChatSkill",
      "deleteChatSkill",
    ]);
    for (const operation of CHAT_CONFIGURATION_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(
        expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN", "BUSINESS_RESOURCE_NOT_FOUND"]),
      );
    }
  });
});
