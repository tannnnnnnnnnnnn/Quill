(async () => {
  try {
    await import(chrome.runtime.getURL("src/contentMain.js"));
  } catch {
    // The page must remain unaffected if the extension is reloaded mid-navigation.
  }
})();
