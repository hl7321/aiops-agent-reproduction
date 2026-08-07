import { createRouter, createWebHistory } from "vue-router";

import FoundationView from "./views/FoundationView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: "/", component: FoundationView }],
});
