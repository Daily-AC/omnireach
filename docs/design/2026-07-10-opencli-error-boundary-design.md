# OpenCLI Error Boundary and Native Bridge Direction

## Problem

A real `omnireach search "gpt5.6" --on douyin` invocation returned zero results and the
TTY summary `1 个源未配置`. Minutes later, the same command succeeded repeatedly from the
same directory and account. OpenCLI doctor, the Chrome extension, and direct Douyin search
were all healthy.

The misleading message comes from Omnireach's error boundary. The shared OpenCLI bridge
turns every nonzero subprocess exit, malformed JSON response, and invalid response shape
into `AdapterUnavailable`. The dispatcher therefore labels runtime failures as
`unavailable`, and the TTY renderer hides their details behind a generic configuration
count.

## Immediate Goal

Report OpenCLI runtime failures as execution failures with their original detail while
preserving actionable unavailable errors for a genuinely missing OpenCLI binary.

## Immediate Design

Add `OpenCLICommandError`, a `RuntimeError` subclass owned by
`omnireach.adapters._opencli`. It carries the source name through its message and represents
an installed OpenCLI command that failed to execute or returned an unusable contract.

`run_opencli_json` will use the error types as follows:

- OpenCLI is absent from `PATH`: `AdapterUnavailable`, unchanged.
- OpenCLI exits nonzero: `OpenCLICommandError` containing stderr, or stdout when stderr is
  empty.
- OpenCLI returns malformed JSON: `OpenCLICommandError` containing the JSON decode detail.
- OpenCLI returns a non-list/non-results shape: `OpenCLICommandError` describing the
  contract violation.
- A valid list of result dictionaries: return normally.

No dispatcher change is required. Its existing generic exception branch classifies
`OpenCLICommandError` as `failed`, and the existing TTY failed-error renderer prints the
full detail in red. Missing OpenCLI still follows the unavailable summary and setup hint.

## Considered Alternatives

### Parse individual OpenCLI error strings into unavailable versus failed

This could recognize login and extension messages, but OpenCLI error text is not a stable
typed contract across adapters. String heuristics would recreate the same classification
drift at a different layer. It is rejected for this patch.

### Mark every adapter error as failed

This would expose details but regress the quiet UX for genuinely unconfigured keys and
missing binaries. It is rejected because `AdapterUnavailable` remains useful when applied
only to readiness conditions.

### Add automatic retries

Retries may help a reconnecting bridge but would hide the classification bug and multiply
requests to login-walled platforms. Retry policy needs separate evidence and is out of
scope.

## Testing

- A missing OpenCLI binary still raises `AdapterUnavailable`.
- A nonzero OpenCLI subprocess exit raises `OpenCLICommandError` with the upstream detail.
- Malformed JSON and invalid result shapes raise `OpenCLICommandError`.
- Dispatcher converts `OpenCLICommandError` to `SourceError(category="failed")`.
- TTY search output prints the Douyin failure detail and does not print the generic
  `源未配置` summary for that error.
- Existing cancellation, successful parsing, and missing-dependency tests remain green.
- Real Douyin search still returns live results after the error-boundary change.

## Removing the OpenCLI Dependency

Omnireach can stop depending on the OpenCLI executable, but not by pretending the browser
and authenticated-session problem disappears. Twitter, Douyin, Xiaohongshu, and similar
sources still need a trusted component inside the user's Chrome session.

The recommended migration is incremental:

1. Introduce a small internal `BrowserTransport` interface after this bugfix. OpenCLI is
   the first implementation, with no behavior change.
2. Build an Omnireach-owned, read-only Chrome extension plus a local Python bridge. The
   extension exposes only request execution and response capture for allowlisted domains;
   it does not expose arbitrary page control.
3. Migrate one source with strong real fixtures, preferably Douyin or Twitter, to prove
   cookie inheritance, request signing, cancellation, and silent tab cleanup.
4. Move remaining sources one at a time, retaining OpenCLI as a fallback until parity is
   demonstrated.

Directly decrypting Chrome's cookie database is rejected: it is platform-specific, fights
Chrome encryption and profile locking, and still does not solve site-specific request
signing. Attaching CDP to the user's already-running normal Chrome is also unreliable
because modern Chrome requires remote debugging to be enabled at process launch and often
requires a separate user data directory. Rebuilding a smaller, read-only bridge is more
work than shelling out to OpenCLI, but it is the path that actually gives Omnireach control
of its dependency depth and user experience.

## Release

Ship the immediate classification fix as `0.13.1-alpha`. The native bridge direction is
documented only and does not change runtime behavior in this release.
