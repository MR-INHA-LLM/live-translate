// FE 브라우저 검증 — 3분할 레이아웃 + 한글 IME 초벌 + 전송→고객화면.
// 게이트웨이 + FE(nginx) + vLLM이 떠 있어야 한다. SMOKE_URL로 대상 지정.
import { chromium } from "@playwright/test";

const URL = process.env.SMOKE_URL ?? "http://localhost:18090";
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

// 한글 IME 조합 입력 시뮬레이션 (compositionstart → input → compositionend)
async function imeType(text) {
  await page.evaluate((t) => {
    const ta = document.querySelector("textarea");
    ta.focus();
    ta.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }));
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(ta, t);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    ta.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: t }));
  }, text);
}

try {
  await page.goto(URL, { waitUntil: "networkidle" });

  // 3분할 존재
  for (const sel of [".col.side", ".col.work", ".col.customer"]) {
    await page.waitForSelector(sel, { timeout: 15000 });
  }
  await page.waitForSelector("textarea:not([disabled])", { timeout: 20000 });

  // 한글 IME로 입력 → 초벌 미리보기 뜨는지 (핵심: IME 버그 수정 검증)
  await imeType("내일 오후 회의를 금요일로 옮겨 주세요");
  await page.waitForSelector(".draftprev", { timeout: 25000 });
  const draft = (await page.textContent(".draftprev"))?.replace(/\s+/g, " ").trim();
  console.log("IME 초벌 미리보기:", draft);

  // 전송 → 작업대 말풍선 + 고객화면 반영
  const before = await page.locator(".work .row.mine").count();
  await page.click(".send");
  await page.waitForFunction(
    (n) => document.querySelectorAll(".work .row.mine").length > n,
    before,
    { timeout: 40000 },
  );
  const trans = (await page.locator(".work .row.mine").last().locator(".trans").textContent())
    ?.replace(/^→ \w+/, "").trim();
  const cust = (await page.locator(".customer .cbubble").last().textContent())?.trim();
  console.log("작업대 번역:", trans);
  console.log("고객 화면:", cust);

  if (!draft || draft.length < 5) throw new Error("IME 초벌이 안 뜸 (버그 미수정)");
  if (!trans || trans.length < 5) throw new Error("작업대 번역 없음");
  if (!cust || cust.length < 5) throw new Error("고객 화면 미반영");
  if (errors.length) throw new Error("콘솔 에러: " + errors.join(" | "));
  console.log("\nSMOKE PASS ✅  3분할 + 한글 IME 초벌 + 고객화면 동작");
  await browser.close();
} catch (e) {
  console.error("SMOKE FAIL ❌", e.message);
  if (errors.length) console.error("errors:", errors);
  await browser.close();
  process.exit(1);
}
