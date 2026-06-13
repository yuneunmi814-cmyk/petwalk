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
};

export default config;
