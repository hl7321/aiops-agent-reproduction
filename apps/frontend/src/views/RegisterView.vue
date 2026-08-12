<script setup lang="ts">
import { ArrowRight, UserRoundPlus } from "lucide-vue-next";
import { ref } from "vue";
import { useRouter } from "vue-router";

import { publicConfig } from "../config";
import { useAuthStore } from "../stores/auth";
import { useFeedbackStore } from "../stores/feedback";

const auth = useAuthStore();
const feedback = useFeedbackStore();
const router = useRouter();
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const submitting = ref(false);

async function submit(): Promise<void> {
  if (password.value !== confirmPassword.value) {
    feedback.show("error", "两次输入的密码不一致");
    return;
  }
  submitting.value = true;
  const payload = { email: email.value, password: password.value };
  try {
    await auth.register(payload);
    await auth.login(payload);
    feedback.show("success", "账号创建成功");
    await router.replace("/chat");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "注册失败，请重试");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro" aria-labelledby="register-product-title">
      <div class="brand-mark"><UserRoundPlus :size="22" aria-hidden="true" /></div>
      <p class="eyebrow">安全的本地身份</p>
      <h1 id="register-product-title">{{ publicConfig.title }}</h1>
      <p>创建本地账号后进入桌面工作台。业务数据不会因登出而被删除。</p>
    </section>
    <section class="auth-panel" aria-labelledby="register-title">
      <div>
        <p class="eyebrow">开始使用</p>
        <h2 id="register-title">创建账号</h2>
        <p class="auth-panel__hint">密码只会以安全哈希形式保存在本机数据库。</p>
      </div>
      <form @submit.prevent="submit">
        <label>邮箱<input v-model="email" type="email" autocomplete="email" required /></label>
        <label>密码<input v-model="password" type="password" autocomplete="new-password" minlength="8" required /></label>
        <label>确认密码<input v-model="confirmPassword" name="confirmPassword" type="password" autocomplete="new-password" required /></label>
        <button class="button button--primary" type="submit" :disabled="submitting">
          {{ submitting ? "正在创建" : "创建并登录" }}<ArrowRight :size="18" aria-hidden="true" />
        </button>
      </form>
      <p class="auth-switch">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
    </section>
  </main>
</template>
