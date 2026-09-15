const config = {
  appId: 'ir.temce.golddesk',
  appName: 'GoldDesk',
  webDir: 'out',
  bundledWebRuntime: false,
  backgroundColor: '#09090b',
  // iOS
  ios: {
    contentInset: 'always',
    backgroundColor: '#09090b',
  },
  // Android
  android: {
    backgroundColor: '#09090b',
    allowMixedContent: false,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
  // Plugins
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#09090b',
      showSpinner: false,
      androidSpinnerStyle: 'small',
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
};

export default config;
