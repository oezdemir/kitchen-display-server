# Kitchen Display Host — API Specification

**Audience:** the AI agent (or developer) building the host service that feeds a Seeed reTerminal E1001 running the modified CrossPoint Reader firmware as a kitchen display.

**Goal:** the host is a small HTTP service running on a home computer (or always-on device like a Raspberry Pi / NAS). On a schedule it fetches:
- the lunch menus for two children from their respective school sources
- the local weather forecast

…then renders a single 800×480 1-bit BMP image and serves it via the API below. The device wakes from deep sleep on its own schedule, pulls the BMP, displays it, and goes back to sleep.

The host is the **only intelligence** in the system. The device just fetches, validates, and displays. Everything visible on the e-ink (text, layout, icons) is your responsibility.

---

## 1. Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/sleep.bmp` | GET | Returns the rendered kitchen-display image (gzip-compressed BMP) |

That's it. v1 has exactly one endpoint. (`/api/v1/dashboard.json` is reserved for a future "interactive when device is awake" mode but is **not** implemented in firmware v1 — don't build it.)

---

## 2. Request

```
GET /api/v1/sleep.bmp HTTP/1.1
Host: <your-host>:<your-port>
Authorization: Bearer <shared-secret-token>
If-None-Match: "<previously-stored-etag>"        ← optional; absent on first fetch
User-Agent: CrossPoint-reTerminal/<version> (kitchen-display)
X-Battery-Pct: <0..100>                          ← informational; you may log it
```

- The device sends `If-None-Match` only when it has a previously-stored ETag from a prior `200`.
- The device follows redirects (HTTPC_STRICT_FOLLOW_REDIRECTS) but you don't need to use them.
- `User-Agent` is fixed-format; you can use it to distinguish device requests from a browser/curl.

---

## 3. Responses

### 3.1 `200 OK` — fresh image

```
HTTP/1.1 200 OK
Content-Type: image/bmp
Content-Encoding: gzip
ETag: "<opaque-string-up-to-128-chars>"
Cache-Control: max-age=3600                ← informational; device ignores it

<gzipped body — see §4 for format>
```

**Required headers:**
- `Content-Type: image/bmp`
- `Content-Encoding: gzip` — the body MUST be gzipped (see §4 for why and how)
- `ETag` — opaque string, max ~128 chars including the surrounding quotes. The device persists this and sends it back as `If-None-Match` on the next request.

**ETag semantics:** the ETag MUST change when the visible content changes, and SHOULD remain stable when the visible content is the same. A SHA-256 hash of the BMP body (truncated to 16 hex chars) is fine.

### 3.2 `304 Not Modified` — image unchanged

```
HTTP/1.1 304 Not Modified
ETag: "<same-etag-the-device-sent>"
```

No body. Send this when the device's `If-None-Match` matches the current ETag.

**Important:** see §5 for when you MUST NOT return 304.

### 3.3 Error responses

The device treats anything that isn't `200` or `304` as "Failed → show device default image" and preserves its cached BMP.

- `401 Unauthorized` — bad/missing token. Return this if `Authorization` header is wrong.
- `4xx` / `5xx` — host bug or unrecoverable error. Reserve `5xx` for actual host bugs (crashed scraper, misconfigured server). Don't use it for "I couldn't fetch upstream menu data" — see §5.

---

## 4. BMP format requirements (hard contract)

The device's BMP parser will reject anything that doesn't match. Test your output before deploying.

| Property | Requirement |
|---|---|
| Width | **Exactly 800** pixels |
| Height | **Exactly 480** pixels |
| Format | Standard uncompressed Windows BMP (BI_RGB), `.bmp` magic `0x42 0x4D` ("BM") |
| Color depth | **1-bit monochrome preferred** (smallest, sharpest text on e-ink). 4-bit and 8-bit grayscale also accepted. |
| RLE | **Not** allowed (no BI_RLE4 / BI_RLE8). Uncompressed pixel data only. |
| Wire encoding | **gzip** (HTTP `Content-Encoding: gzip` on the response, OR alternatively serve a `.bmp.gz` file with `Content-Type: application/gzip` — semantics are identical to the device) |

**Size:** an 800×480 1-bit BMP is ~48 KB raw, typically ~2–10 KB after gzip. The device streams it through gzip→file→inflate→file with very little RAM use, so payload size is forgiving.

**Layout suggestions (not part of the contract):**
- Reserve ~80 px at the top for a header strip (date, weather summary)
- Two side-by-side menu cards below for the two daughters
- Use large, readable fonts — kitchen distance, not reading distance
- Pure black-and-white text reads best on e-ink; reserve grayscale for icons/photos
- The display orientation is portrait by default — your 800×480 should be designed accordingly

---

## 5. The "no lies" contract — MUST follow

This is the rule that lets the device firmware stay simple. **Read it carefully.**

A `304 Not Modified` response is a positive assertion by the host: *"I have confirmed this image is still the right one to show."* You **MUST NOT** return `304` if your underlying data fetch failed. Specifically:

```
function handle_request(request):
  current_data = fetch_upstream_menus_and_weather()

  if current_data.fetch_failed:
      # Generate a "data unavailable" placeholder BMP and serve THAT.
      # Do not return 304 (would tell device "stale image is still correct").
      bmp = render("Kitchen display: data unavailable", timestamp=now)
      etag = hash(bmp)
      return 200 OK, etag, gzip(bmp)

  bmp = render(current_data)
  etag = hash(bmp)

  if request.if_none_match == etag:
      return 304 Not Modified, etag         # confirmed: no change

  return 200 OK, etag, gzip(bmp)
```

Three valid host responses, summarised:

| Host situation | Response |
|---|---|
| Upstream fetched, content unchanged | `304 Not Modified` |
| Upstream fetched, content changed | `200 OK` + new BMP + new ETag |
| Upstream fetch FAILED (and you want to control the message) | `200 OK` + freshly-rendered placeholder BMP + new ETag |
| Upstream fetch FAILED (and you'd rather defer to device default) | `503 Service Unavailable` |

**Forbidden:** returning `304` when your upstream data is stale or unverified.

The reason: the device doesn't second-guess the host. It only classifies each fetch as `200` / `304` / `Failed` and trusts the host's assertion. If you lie via 304, the device will keep showing yesterday's lunch menu.

---

## 6. Auth

- Generate a random ~32-byte token once, e.g. `openssl rand -hex 32`.
- Configure the same token on the host and on the device (via the device's web UI: `http://<device-ip>/kitchen-settings`).
- Reject mismatching `Authorization: Bearer <token>` headers with `401`.

This is a single shared secret in cleartext on both ends. Threat model is low (LAN-only device, no privileged data behind the API). If the token leaks, attacker can fetch a lunch-menu image. Don't expose the API to the internet.

---

## 7. Operational contract

### What the host MUST do

- Run an HTTP server on a port reachable from the device on home WiFi (default `8080`).
- Be reachable when the device wakes. Wake-up cadence is configured on the device — typical values are every 30 min (testing) or every 12 h (production). If your machine sleeps when the lid closes, the device sees "unreachable" and falls back to its default image (or stays on the cached image, depending on whether `/sleep-default.bmp` is present on its SD card).
- Bind to a stable address. Either:
  - Give the host machine a DHCP reservation (recommended — easiest), or
  - Use mDNS (`<name>.local`) and ensure your router supports mDNS reflection.

### What the host should NOT do

- **Do not push to the device** — pull-only by design. The device cannot accept inbound connections from deep sleep.
- **Do not authenticate users** — single shared token, single device.
- **Do not persist device state** — the device manages its own ETag.
- **Do not expose this API to the internet.**

---

## 8. Reference implementations

### 8.1 Mock host (testing)

A minimal Python mock implementing this contract is in the firmware repo at:

```
code/crosspoint-reader/scripts/mock_kitchen_host.py
```

It supports `--mode normal | stale | garbage | down` for exercising the device's failure paths. Use it as a sanity-check oracle for your real host's behavior — your host should respond identically to the same client requests.

Example invocation:

```bash
pip install pillow
python3 scripts/mock_kitchen_host.py \
  --port 18080 \
  --token <your-shared-token> \
  --mode normal
```

### 8.2 Recommended starter stack for the real host

Not part of the contract — pick whatever suits you. As reference:

- **Language:** Python 3.10+ is convenient (Pillow for BMP rendering, requests for upstream scraping)
- **Framework:** FastAPI or Flask are both fine for the ~50-line HTTP server
- **Rendering:** Pillow's `Image.new("1", (800, 480), 1)` + `ImageDraw` is sufficient
- **Scheduling:** A separate periodic job (cron, APScheduler) renders + caches the BMP every N hours. The HTTP handler serves the cached file. This decouples render time from request latency and avoids re-rendering on every device wake.
- **Deployment:** Run as a systemd service (Linux) or LaunchAgent (macOS), or a Docker container. Anything that survives reboots and stays running.

A reasonable architecture:

```
┌──────────────────────────────────────────────────────────────┐
│ Host machine                                                 │
│                                                              │
│  ┌───────────────────────┐   ┌──────────────────────────┐    │
│  │ Scheduled renderer    │   │ HTTP server (port 8080)  │    │
│  │ (every N hours):      │   │                          │    │
│  │  1. fetch menus       │   │ GET /api/v1/sleep.bmp:   │    │
│  │  2. fetch weather     │   │   - check Bearer auth    │    │
│  │  3. compose layout    │   │   - read cache           │    │
│  │  4. render PIL→BMP    │──>│   - compare If-None-Match│    │
│  │  5. write cache.bmp   │   │   - return 200 or 304    │    │
│  │     + cache.etag      │   │                          │    │
│  └───────────────────────┘   └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
       │
       └─ HTTP over LAN ─→  Seeed reTerminal E1001 (kitchen display)
```

---

## 9. Putting it together

To build a working host:

1. **Implement §3 + §4 + §5** — the API endpoint with correct status codes, BMP format, and the no-lies rule. This is the core contract.
2. **Implement §6** — bearer-token auth.
3. **Build the upstream data layer** — scraping menus from the school sites, fetching weather from a forecast API. This is your hardest problem; the device firmware doesn't help with it.
4. **Build the render layer** — Pillow code that takes structured data (menus, weather, date) and outputs a 800×480 1-bit BMP.
5. **Wire scheduling** — periodically (every N hours) re-render and refresh the cache.
6. **Test against the mock client** — point a curl request at your service mimicking the device's request format. Verify `200`, `304`, and the failure paths.
7. **Deploy** — make sure the service starts at boot and your machine doesn't sleep during scheduled device wake times.

---

## 10. Spec changes / questions

If something here is unclear or you need to negotiate a change, the firmware spec at `docs/superpowers/specs/2026-05-09-kitchen-display-design.md` has the device-side reasoning. Anything in §1–§7 of THIS doc is the binding contract; everything else is advisory.
