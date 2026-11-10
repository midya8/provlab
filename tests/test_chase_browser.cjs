"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict"),
  fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path"),
  { spawn, execFileSync } = require("node:child_process"),
  { waitForDebugger } = require("./chrome_support.cjs");
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
async function stop(browser) {
  try {
    process.kill(-browser.pid, "SIGTERM");
  } catch {}
  if (browser.exitCode === null)
    await Promise.race([
      new Promise((r) => browser.once("exit", r)),
      delay(3000),
    ]);
  try {
    process.kill(-browser.pid, "SIGKILL");
  } catch {}
}
test(
  "actual Chrome chase quotients, dependencies, traces and trusted certificate downloads",
  { timeout: 180000 },
  async () => {
    const server = require("node:http").createServer((req, res) => {
      try {
        const file = path.join(
          __dirname,
          "../docs",
          req.url === "/" ? "index.html" : req.url,
        );
        res.setHeader(
          "Content-Type",
          {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
          }[path.extname(file)] || "text/plain",
        );
        res.end(fs.readFileSync(file));
      } catch {
        res.statusCode = 404;
        res.end("not found");
      }
    });
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), "provlab-")),
      browser = spawn(
        process.env.CHROME_BIN || "google-chrome",
        [
          "--headless",
          "--no-sandbox",
          "--disable-gpu",
          "--disable-extensions",
          "--disable-dev-shm-usage",
          "--remote-debugging-port=0",
          `--user-data-dir=${profile}`,
          "about:blank",
        ],
        { detached: true, stdio: ["ignore", "ignore", "pipe"] },
      );
    let ws,
      startupError,
      diagnostics = "";
    browser.on("error", (e) => (startupError = e));
    browser.stderr.on(
      "data",
      (d) => (diagnostics = (diagnostics + d).slice(-4000)),
    );
    try {
      for (
        let i = 0;
        i < 1200 &&
        !startupError &&
        browser.exitCode === null &&
        !fs.existsSync(path.join(profile, "DevToolsActivePort"));
        i++
      )
        await delay(25);
      assert.ok(
        fs.existsSync(path.join(profile, "DevToolsActivePort")),
        startupError?.message || diagnostics,
      );
      const port = fs
          .readFileSync(path.join(profile, "DevToolsActivePort"), "utf8")
          .split("\n")[0],
        tab = await waitForDebugger(`http://127.0.0.1:${port}/json/list`, {
          alive: () => browser.exitCode === null && !startupError,
        });
      ws = new WebSocket(tab.webSocketDebuggerUrl);
      await new Promise((r, j) => {
        ws.onopen = r;
        ws.onerror = j;
      });
      let seq = 0;
      const pending = new Map(),
        errors = [],
        downloads = new Map();
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.method === "Browser.downloadWillBegin")
          downloads.set(m.params.guid, { ...m.params, state: "started" });
        if (
          m.method === "Browser.downloadProgress" &&
          downloads.has(m.params.guid)
        )
          Object.assign(downloads.get(m.params.guid), m.params);
        if (m.method === "Runtime.exceptionThrown") errors.push(m.params);
        if (pending.has(m.id)) {
          const { r, j } = pending.get(m.id);
          pending.delete(m.id);
          m.error ? j(Error(JSON.stringify(m.error))) : r(m.result);
        }
      };
      const call = (method, params = {}) =>
          new Promise((r, j) => {
            const id = ++seq;
            pending.set(id, { r, j });
            ws.send(JSON.stringify({ id, method, params }));
          }),
        js = async (expression) => {
          const r = await call("Runtime.evaluate", {
            expression,
            returnByValue: true,
            awaitPromise: true,
          });
          if (r.exceptionDetails)
            throw Error(JSON.stringify(r.exceptionDetails));
          return r.result.value;
        };
      await call("Runtime.enable");
      await call("Page.enable");
      await call("Page.navigate", {
        url:
          process.env.CONTAINMENT_URL ||
          `http://127.0.0.1:${server.address().port}/chase.html`,
      });
      for (
        let i = 0;
        i < 500 && !(await js("Boolean(window.chaseReport)"));
        i++
      )
        await delay(20);
      assert.ok(await js("window.chaseReport"));
      const controls = JSON.parse(
          fs.readFileSync(
            path.join(__dirname, "../docs/chase-controls.json"),
            "utf8",
          ),
        ),
        reports = JSON.parse(
          execFileSync(
            process.env.PYTHON || "python",
            [
              "-c",
              'import json;from provlab.chase import analyze;print(json.dumps([analyze(c["input"])for c in json.load(open("docs/chase-controls.json"))]))',
            ],
            { maxBuffer: 128 * 1024 * 1024 },
          ),
        );
      const set = (id, value, event = "change") =>
          js(
            `document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event(${JSON.stringify(event)}))`,
          ),
        text = (id) =>
          js(`document.getElementById(${JSON.stringify(id)}).textContent`),
        rows = (id) =>
          js(
            `Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' tbody tr'),tr=>Array.from(tr.children,td=>td.textContent))`,
          ),
        tuple = (x) => "(" + x.join(", ") + ")",
        term = (t) => (Object.hasOwn(t, "var") ? t.var : '"' + t.const + '"'),
        atom = (a) => a.relation + tuple(a.terms.map(term));
      async function shot(name) {
        if (!process.env.SCREENSHOT_DIR) return;
        await js(
          "document.activeElement.blur();window.scrollTo(0,0);new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))",
        );
        const m = await call("Page.getLayoutMetrics");
        const image = await call("Page.captureScreenshot", {
          format: "png",
          captureBeyondViewport: true,
          clip: {
            x: 0,
            y: 0,
            width: await js("innerWidth"),
            height: m.cssContentSize.height,
            scale: 1,
          },
        });
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        fs.writeFileSync(
          path.join(process.env.SCREENSHOT_DIR, "chase-" + name + ".png"),
          Buffer.from(image.data, "base64"),
        );
      }
      const counts = {
        reports: 0,
        directions: 0,
        trace_states: 0,
        subset_selections: 0,
        downloads: 0,
      };
      let lastDownloadGesture = -Infinity;
      for (const width of [1280, 390, 320]) {
        await call("Emulation.setDeviceMetricsOverride", {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: false,
        });
        for (let ci = 0; ci < controls.length; ci++) {
          await set("control", ci);
          const r = reports[ci];
          assert.deepEqual(await js("window.chaseReport"), r);
          counts.reports++;
          for (let di = 0; di < 2; di++) {
            await js(`document.getElementById('${di ? "rl" : "lr"}').click()`);
            const d = r.directions[di];
            counts.directions++;
            assert.equal(
              await js(
                `document.getElementById('${di ? "rl" : "lr"}').getAttribute('aria-pressed')`,
              ),
              "true",
            );
            for (const step of d.chase.trace) {
              await set("step", step.step);
              counts.trace_states++;
              assert.deepEqual(
                await rows("facts"),
                step.state.facts.map((f, i) => [
                  String(i),
                  f.relation + tuple(f.values),
                ]),
              );
              assert.deepEqual(
                await rows("aliases"),
                Object.entries(step.state.aliases),
              );
              assert.equal(await text("current-head"), tuple(step.state.head));
            }
            assert.deepEqual(
              await rows("checks"),
              d.chase.dependency_checks.map((c) => [
                r.input.dependencies[c.dependency].name,
                String(c.body_match_count),
                String(c.violation_count),
                c.satisfied ? "yes" : "no",
              ]),
            );
            for (const [id, ev] of [
              ["source-answers", d.source_evaluation],
              ["target-answers", d.target_evaluation],
            ])
              assert.equal(
                await text(id),
                ev
                  ? ev.answers.map(tuple).join("\n") || "No answers."
                  : "Not evaluated: failed chase.",
              );
            assert.equal(
              await js("document.documentElement.scrollWidth>innerWidth"),
              false,
              JSON.stringify({
                width,
                ci,
                di,
                overflow: await js(
                  `Array.from(document.querySelectorAll('*')).filter(e=>e.getBoundingClientRect().right>innerWidth+1&&getComputedStyle(e).position!=='absolute').map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().right]).slice(0,15)`,
                ),
              }),
            );
            if ([0, 2, 4, 5, 8, 10, 12, 13].includes(ci))
              await shot(`control-${ci}-direction-${di}-${width}`);
          }
          for (const a of r.dependency_atlas) {
            await set("subset", a.mask);
            const selected = await js("window.chaseReport");
            assert.deepEqual(
              selected.input.dependencies,
              a.retained_dependencies.map((i) => r.input.dependencies[i]),
            );
            for (let di = 0; di < 2; di++) {
              assert.equal(
                selected.directions[di].contained,
                a.directions[di].contained,
              );
              assert.equal(
                selected.directions[di].reason,
                a.directions[di].reason,
              );
            }
            counts.subset_selections++;
          }
          await set("subset", 2 ** r.input.dependencies.length - 1);
          await js("document.getElementById('lr').click()");
          if (ci === 0) await shot("default-" + width);
          if (width === 1280) {
            const dir = path.join(profile, "exports");
            fs.mkdirSync(dir, { recursive: true });
            await call("Browser.setDownloadBehavior", {
              behavior: "allowAndName",
              downloadPath: dir,
              eventsEnabled: true,
            });
            const previous = new Set(downloads.keys());
            await call("Page.bringToFront");
            await js(
              "window.lastDownloadClick=null;document.getElementById('download').addEventListener('click',e=>{window.lastDownloadClick={trusted:e.isTrusted,active:navigator.userActivation.isActive}},{once:true});document.getElementById('download').scrollIntoView({block:'center'});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))",
            );
            const b = await js(
              "(()=>{const e=document.getElementById('download'),r=e.getBoundingClientRect();if(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)!==e)throw Error('download not hit target');return{x:r.x+r.width/2,y:r.y+r.height/2}})()",
            );
            await delay(
              Math.max(0, 250 - (performance.now() - lastDownloadGesture)),
            );
            lastDownloadGesture = performance.now();
            for (const type of ["mousePressed", "mouseReleased"])
              await call("Input.dispatchMouseEvent", {
                type,
                ...b,
                button: "left",
                clickCount: 1,
              });
            assert.deepEqual(await js("window.lastDownloadClick"), {
              trusted: true,
              active: true,
            });
            let item;
            for (let k = 0; k < 800; k++) {
              item = [...downloads.values()].find((d) => !previous.has(d.guid));
              if (item?.state === "completed" || item?.state === "canceled")
                break;
              await delay(25);
            }
            assert.ok(item);
            assert.equal(item.state, "completed");
            assert.equal(
              item.suggestedFilename,
              "provlab-chase-certificate.json",
            );
            const file = path.join(dir, item.guid);
            assert.deepEqual(JSON.parse(fs.readFileSync(file)), r);
            execFileSync(process.env.PYTHON || "python", [
              "-m",
              "provlab.chase_cli",
              file,
              "--verify",
            ]);
            fs.unlinkSync(file);
            counts.downloads++;
          }
        }
      }
      await set("control", 0);
      await set("subset", 0);
      assert.equal((await js("window.chaseReport")).set_equivalent, false);
      await shot("no-assumptions-320");
      for (const raw of [
        "{}",
        '{"schema":[],"schema":[]}',
        "NaN",
        " ".repeat(65537),
      ]) {
        await set("editor", raw, "input");
        await js("document.getElementById('run').click()");
        assert.equal(await js("window.chaseReport"), null);
        assert.equal(await text("verdict"), "");
        assert.equal(
          await js("document.getElementById('download').disabled"),
          true,
        );
        assert.match(await text("status"), /^Input rejected:/);
      }
      await shot("invalid-320");
      await set("control", 0);
      assert.deepEqual(await js("window.chaseReport"), reports[0]);
      assert.deepEqual(errors, []);
      console.log(JSON.stringify(counts));
    } finally {
      ws?.close();
      await stop(browser);
      server.closeAllConnections();
      await new Promise((r) => server.close(r));
      await fs.promises.rm(profile, {
        recursive: true,
        force: true,
        maxRetries: 20,
        retryDelay: 100,
      });
    }
  },
);
