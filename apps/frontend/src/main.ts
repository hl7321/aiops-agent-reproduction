import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { createAppRouter } from "./router";
import { useAuthStore } from "./stores/auth";
import "./styles/tokens.css";
import "./styles/global.css";

const pinia = createPinia();
const auth = useAuthStore(pinia);
const router = createAppRouter(auth);

createApp(App).use(pinia).use(router).mount("#app");
