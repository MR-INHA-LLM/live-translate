// FE 브라우저 스모크 — 실제 채팅으로 초벌 미리보기 + 전송→최종 번역 말풍선 검증.
// 게이트웨이(:8000) + vite preview(:5173) + vLLM(:8001)가 떠 있어야 한다.
import { chromium } from "@playwright/test";

const URL = "http://localhost:5173";
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

try {
  await page.goto(URL, { waitUntil: "networkidle" });
  // 세션 생성 → textarea 활성화 대기
  await page.waitForSelector("textarea:not([disabled])", { timeout: 20000 });

  // 한국어 입력 → 초벌 미리보기(id·en) 뜨는지
  await page.fill("textarea", "내일 오후 회의를 금요일로 옮겨 주세요");
  await page.waitForSelector(".draftprev", { timeout: 25000 });
  const draft = (await page.textContent(".draftprev"))?.replace(/\s+/g, " ").trim();
  console.log("초벌 미리보기:", draft);

  // 전송 → 새 mine 말풍선 + 번역
  const before = await page.locator(".row.mine").count();
  await page.click(".send");
  await page.waitForFunction(
    (n) => document.querySelectorAll(".row.mine").length > n,
    before,
    { timeout: 40000 },
  );
  const last = page.locator(".row.mine").last();
  const trans = (await last.locator(".trans").textContent())?.replace(/^보냄/, "").trim();
  const witCount = await last.locator(".wit").count();
  const wit = witCount ? (await last.locator(".wit").textContent())?.trim() : "";
  console.log("최종 말풍선:", trans);
  console.log("witness:", wit);

  if (!trans || trans.length < 5) throw new Error("번역 말풍선이 비어있음");
  if (errors.length) throw new Error("콘솔 에러: " + errors.join(" | "));
  console.log("\nSMOKE PASS ✅  (FE→게이트웨이→vLLM 브라우저 경로 동작)");
  await browser.close();
} catch (e) {
  console.error("SMOKE FAIL ❌", e.message);
  if (errors.length) console.error("errors:", errors);
  await browser.close();
  process.exit(1);
}
