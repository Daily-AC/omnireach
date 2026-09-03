# Extension self-reload verification

Verified on 2026-09-03 against the live bridge, Chrome 152.0.7977.65 on macOS.

## The problem it removes

`omnireach bridge install` copies the extension into
`~/.omnireach/chrome-extension`, but a running Chrome does not load the new
files. An idle MV3 service-worker restart does not pick them up either —
measured: 50 seconds of idle time, still the old `EXTENSION_VERSION`. The only
route was a human clicking **Reload** at `chrome://extensions`, and Chrome 136+
no longer exposes extension targets to CDP, so no automation can do it:
`Target.getTargets` with an all-types filter returns only `page`, `browser_ui`
and `tab`. Shipping the creator catalog in #46 cost four such interruptions.

## The risk that had to be ruled out

`chrome.runtime.reload()` destroys the offscreen document, and that document is
the only thing polling the bridge. Only the service worker can recreate it, and
only an event wakes an idle worker — so if Chrome did not restart the worker
after a reload, the bridge would stay dead until the browser restarted.

**It does restart.** The measurement below is the whole reason this shipped
rather than staying a design note.

## Measurement

With extension 0.4.0 connected, the *installed* copy on disk was edited to
0.4.1 without touching the repository, so the running extension and the files
on disk deliberately disagreed:

```
installed 0.4.1  connected 0.4.0  reload_required True
$ omnireach bridge reload --json
{"reloaded": true, "installed_version": "0.4.1", "connected_version": "0.4.1"}
real  1.8s
```

The new code was loaded, the worker came back on its own, the offscreen
document was recreated, and the bridge reconnected — in 1.8 seconds, with no
human action.

The round trip back to 0.4.0 (`bridge install && bridge reload`) also reported
`reloaded: true`, and a real `omnireach author` call immediately afterwards
returned two works with `errors=[]`, confirming the bridge was fully functional
and not merely answering `system.ping`.

## What is not proven here

The `alarms` keepalive is a safety net for an offscreen document that dies
without the worker noticing. That state could not be forced on demand, so the
alarm is verified only as far as its listener being registered and the manifest
permission being accepted by Chrome on load. The reload path above never needed
it, which is the expected outcome — the alarm exists for the case where the
reload path is not what killed the document.
