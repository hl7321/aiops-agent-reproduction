<script setup lang="ts">
import { ArrowRight, LockKeyhole } from "lucide-vue-next";
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { publicConfig } from "../config";
import AppErrorState from "../components/states/AppErrorState.vue";
import { resolveSafeRedirect } from "../router";
import { useAuthStore } from "../stores/auth";
import { useFeedbackStore } from "../stores/feedback";

const auth = useAuthStore();
const feedback = useFeedbackStore();
const route = useRoute();
const router = useRouter();
const email = ref("");
const password = ref("");
const submitting = ref(false);

async function submit(): Promise<void> {
  submitting.value = true;
  try {
    await auth.login({ email: email.value, password: password.value });
    feedback.show("success", "登录成功");
    await router.replace(resolveSafeRedirect(route.query.redirect));
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "登录失败，请重试");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro" aria-labelledby="login-product-title">
      <div class="brand-mark"><LockKeyhole :size="22" aria-hidden="true" /></div>
      <p class="eyebrow">智能 ONCALL 工作台</p>
      <h1 id="login-product-title">{{ publicConfig.title }}</h1>
      <p>连接团队知识与运维流程的桌面工作空间。当前提供安全认证与应用壳。</p>
    </section>
    <section class="auth-panel" aria-labelledby="login-title">
      <div>
        <p class="eyebrow">欢迎回来</p>
        <h2 id="login-title">登录工作台</h2>
        <p class="auth-panel__hint">使用已注册的本地账号继续。</p>
      </div>
      <AppErrorState
        v-if="auth.status === 'error' && auth.errorMessage"
        title="认证恢复失败"
        :message="auth.errorMessage"
      />
      <form @submit.prevent="submit">
        <label>邮箱<input v-model="email" type="email" autocomplete="email" required /></label>
        <label>密码<input v-model="password" type="password" autocomplete="current-password" required /></label>
        <button class="button button--primary" type="submit" :disabled="submitting">
          {{ submitting ? "正在登录" : "登录" }}<ArrowRight :size="18" aria-hidden="true" />
        </button>
      </form>
      <p class="auth-switch">还没有账号？<RouterLink to="/register">创建账号</RouterLink></p>
    </section>
  </main>
</template>
