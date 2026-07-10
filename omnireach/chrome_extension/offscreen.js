(function startBridgePolling() {
  "use strict";

  const config = globalThis.OMNIREACH_BRIDGE_CONFIG;
  const retryDelayMs = 500;

  function delay(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  function headers() {
    return {
      Authorization: `Bearer ${config.token}`,
      "Content-Type": "application/json",
    };
  }

  async function submitResult(result) {
    const response = await fetch(`${config.baseUrl}/v1/result`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(result),
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`bridge result rejected with HTTP ${response.status}`);
    }
  }

  async function pollOnce() {
    const response = await fetch(`${config.baseUrl}/v1/job`, {
      headers: headers(),
      cache: "no-store",
    });
    if (response.status === 204) return;
    if (!response.ok) {
      throw new Error(`bridge poll failed with HTTP ${response.status}`);
    }
    const job = await response.json();
    let result;
    try {
      result = await chrome.runtime.sendMessage({ type: "run-job", job });
      if (!result || result.id !== job.id || typeof result.ok !== "boolean") {
        throw new Error("service worker returned an invalid result envelope");
      }
    } catch (error) {
      result = {
        id: job.id,
        ok: false,
        error: {
          kind: "runtime",
          message: error instanceof Error ? error.message : String(error),
        },
      };
    }
    await submitResult(result);
  }

  async function pollForever() {
    if (!config || !config.baseUrl || !config.token) {
      throw new Error("native bridge configuration is missing");
    }
    for (;;) {
      try {
        await pollOnce();
      } catch {
        // The CLI owns the short-lived server, so connection failures are normal.
      }
      await delay(retryDelayMs);
    }
  }

  void pollForever();
})();
