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
  "actual Chrome every output, world, token and trusted certificate download",
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
          process.env.PROVLAB_URL ||
          `http://127.0.0.1:${server.address().port}/`,
      });
      for (let i = 0; i < 500 && !(await js("Boolean(window.provReport)")); i++)
        await delay(20);
      assert.ok(await js("window.provReport"));
      const controls = JSON.parse(
          fs.readFileSync(
            path.join(__dirname, "../docs/controls.json"),
            "utf8",
          ),
        ),
        reports = JSON.parse(
          execFileSync(
            process.env.PYTHON || "python",
            [
              "-c",
              'import json;from provlab import analyze;print(json.dumps([analyze(c["input"])for c in json.load(open("docs/controls.json"))]))',
            ],
            { maxBuffer: 128 * 1024 * 1024 },
          ),
        );

      const set = (id, value, event = "change") =>
        js(
          `document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event(${JSON.stringify(event)}))`,
        );
      const text = (id) =>
        js(`document.getElementById(${JSON.stringify(id)}).textContent`);
      const rows = (id) =>
        js(
          `Array.from(document.querySelectorAll('#'+${JSON.stringify(id)}+' tbody tr'),tr=>Array.from(tr.children,td=>td.textContent))`,
        );
      const listed = (x) => "{" + x.join(", ") + "}";
      async function shot(name) {
        if (!process.env.SCREENSHOT_DIR) return;
        await js(
          'document.activeElement.blur();window.scrollTo(0,0);document.querySelectorAll("textarea").forEach(e=>e.scrollTop=0);new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))',
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
          path.join(process.env.SCREENSHOT_DIR, name + ".png"),
          Buffer.from(image.data, "base64"),
        );
      }
      const counts = {
        reports: 0,
        outputs: 0,
        worldRows: 0,
        worldSelections: 0,
        downloads: 0,
      };
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
          assert.deepEqual(await js("window.provReport"), r);
          assert.equal(await text("why"), controls[ci].why);
          counts.reports++;
          assert.deepEqual(
            await rows("facts"),
            r.input.relations.flatMap((rel) =>
              rel.rows.map((f) => [
                f.id,
                rel.name + "(" + f.values.join(", ") + ")",
                String(f.multiplicity),
                f.probability,
              ]),
            ),
          );
          assert.deepEqual(
            await js(
              'Array.from(document.querySelectorAll("#limits li"),e=>e.textContent)',
            ),
            r.limits,
          );
          for (let oi = 0; oi < r.outputs.length; oi++) {
            await set("output", oi);
            const o = r.outputs[oi];
            counts.outputs++;
            assert.equal(await text("probability"), o.presence_probability);
            assert.equal(await text("bag"), String(o.bag_multiplicity));
            assert.equal(
              await text("arithmetic"),
              o.arithmetic_probability_substitution,
            );
            assert.deepEqual(
              await rows("worlds"),
              o.worlds.map((w) => [
                String(w.mask),
                listed(w.present),
                String(w.holds),
                listed(w.derivation_indices),
                w.mass,
                w.included_mass,
              ]),
            );
            counts.worldRows += o.worlds.length;
            assert.deepEqual(
              await rows("derivations"),
              o.derivation_indices.map((i) => {
                const d = r.derivations[i];
                return [
                  String(i),
                  String(d.branch),
                  JSON.stringify(d.binding),
                  d.tokens.join(" · "),
                  String(d.bag_weight),
                ];
              }),
            );
            for (let mask = 0; mask < o.worlds.length; mask++) {
              const previous = mask ? mask - 1 : 0;
              for (let i = 0; i < r.tokens.length; i++)
                if (((previous ^ mask) >> i) & 1)
                  await js(
                    `document.querySelectorAll('#toggles button')[${i}].click()`,
                  );
              assert.equal(
                await js(
                  'Number(document.getElementById("world-state").dataset.mask)',
                ),
                mask,
              );
              assert.ok(
                (await text("world-state")).includes(
                  "counted " + o.worlds[mask].included_mass,
                ),
              );
              counts.worldSelections++;
            }
            assert.equal(
              await js("document.documentElement.scrollWidth>innerWidth"),
              false,
            );
          }
          if (r.outputs.length) await set("output", 0);
          await shot(`control-${ci}-${width}`);
          if ([0, 2, 5, 9].includes(ci)) {
            await js('document.getElementById("derivation-detail").open=true');
            await shot(`detail-${ci}-${width}`);
            await js('document.getElementById("derivation-detail").open=false');
          }
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
              'window.lastDownloadClick=null;document.getElementById("download").addEventListener("click",e=>{window.lastDownloadClick={trusted:e.isTrusted,active:navigator.userActivation.isActive}}, {once:true})',
            );
            await js(
              'document.getElementById("download").scrollIntoView({block:"center"});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))',
            );
            const b = await js(
              '(()=>{const r=document.getElementById("download").getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()',
            );
            assert.equal(
              await js(
                '(()=>{const e=document.getElementById("download"),r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e})()',
              ),
              true,
              "download center must be the visible hit target",
            );
            for (const type of ["mousePressed", "mouseReleased"])
              await call("Input.dispatchMouseEvent", {
                type,
                ...b,
                button: "left",
                clickCount: 1,
              });
            assert.deepEqual(
              await js("window.lastDownloadClick"),
              { trusted: true, active: true },
              "trusted download click for control " + ci,
            );
            let item;
            for (let k = 0; k < 800; k++) {
              item = Array.from(downloads.values()).find(
                (d) => !previous.has(d.guid),
              );
              if (item?.state === "completed" || item?.state === "canceled")
                break;
              await delay(25);
            }
            assert.ok(
              item,
              "completed native download event required for control " + ci,
            );
            assert.equal(item.state, "completed");
            assert.equal(item.suggestedFilename, "provlab-certificate.json");
            const file = path.join(dir, item.guid);
            assert.deepEqual(JSON.parse(fs.readFileSync(file)), r);
            if (process.env.VERIFY_DOWNLOADS === "1")
              execFileSync(process.env.PYTHON || "python", [
                "-m",
                "provlab",
                file,
                "--verify",
              ]);
            fs.unlinkSync(file);
            counts.downloads++;
          }
        }
      }
      await set("control", 0);
      const edited = structuredClone(controls[0].input);
      edited.relations[0].rows[0].probability = "1";
      await set("input", JSON.stringify(edited), "input");
      await js('document.getElementById("run").click()');
      assert.equal(
        (await js("window.provReport")).outputs[0].presence_probability,
        "1",
      );
      await shot("edited-320");
      for (const raw of [
        "{}",
        '{"relations":[],"relations":[]}',
        "NaN",
        " ".repeat(65537),
      ]) {
        await set("input", raw, "input");
        await js('document.getElementById("run").click()');
        assert.equal(await js("window.provReport"), null);
        assert.equal(
          await js(
            'document.getElementById("download").getAttribute("aria-disabled")',
          ),
          "true",
        );
        assert.equal(await text("results"), "");
        assert.match(await text("status"), /^Rejected:/);
      }
      await shot("invalid-320");
      await set("control", 0);
      assert.deepEqual(await js("window.provReport"), reports[0]);
      await js('document.getElementById("derivation-detail").open=true');
      await shot("expanded-320");
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
