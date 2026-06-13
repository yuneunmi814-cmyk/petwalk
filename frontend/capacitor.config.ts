import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.petwalk.app",
  appName: "PetWalk",
  webDir: "dist",
  server: {
    // Android serves the bundled app over https://localhost; iOS over
    // capacitor://localhost. The backend CORS allows both.
    androidScheme: "https",
  },
  android: {
    // Dev only: the https://localhost WebView calls a cleartext dev backend
    // (http://10.0.2.2:8200). Drop this when the backend is served over HTTPS.
    allowMixedContent: true,
  },
};

export default config;
