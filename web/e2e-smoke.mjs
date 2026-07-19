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

  // 3분할 존재 (좌: 세션 저장소, 중앙: 작업대, 우: 고객 화면)
  for (const sel of [".col.store", ".col.work", ".col.customer"]) {
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
  const mineRow = page.locator(".work .row.mine").last();
  const draftMs = (await mineRow.locator(".trans.draft .ms").textContent())?.trim();
  const finalMs = (await mineRow.locator(".trans.final .ms").textContent())?.trim();
  const trans = (await mineRow.locator(".trans.final").textContent())?.trim();
  const cust = (await page.locator(".customer .cbubble").last().textContent())?.trim();
  console.log("작업대 초벌 소요:", draftMs, "· LLM 소요:", finalMs);
  console.log("고객 화면:", cust);
  if (!/^\d+\.\d+초$/.test(draftMs ?? "")) throw new Error("초벌 소요시간 미표시");
  if (!/^\d+\.\d+초$/.test(finalMs ?? "")) throw new Error("LLM 소요시간 미표시");

  // 검증: 역번역 라인 + 구 정렬 스팬(awesome-align)이 렌더되는지
  const roundTrip = await mineRow.locator(".trans.verify").first().textContent();
  const alignN = await mineRow.locator(".orig .al").count();
  console.log("역번역/확인 라인:", roundTrip?.slice(0, 40), "· 정렬 스팬:", alignN);
  if (!roundTrip || roundTrip.length < 5) throw new Error("역번역/검증 라인 없음");
  if (alignN < 1) throw new Error("구 정렬 스팬 미표시(정렬 서비스 확인)");

  // 고객(태블릿)이 자기 화면에서 입력 → 운영자 작업대에 theirs 로 역번역 수신
  const beforeTheirs = await page.locator(".work .row.theirs").count();
  await page.fill(".customer .device .dfield", "Can you move the meeting to Friday afternoon?");
  await page.click(".customer .device .dsend");
  await page.waitForFunction(
    (n) => document.querySelectorAll(".work .row.theirs").length > n,
    beforeTheirs,
    { timeout: 40000 },
  );
  const inbound = (await page.locator(".work .row.theirs").last().locator(".trans.final").textContent())
    ?.trim();
  console.log("고객→운영자 역번역:", inbound);

  // 세션 저장소: 방금 대화가 좌측 목록에 저장되고, 새 대화→복원이 되는지
  await page.waitForSelector(".convlist .convitem", { timeout: 15000 });
  const convCount = await page.locator(".convlist .convitem").count();
  await page.click(".newconv"); // 새 대화 → 작업대 비움
  await page.waitForFunction(
    () => document.querySelectorAll(".work .row").length === 0,
    null,
    { timeout: 5000 },
  );
  await page.click(".convlist .convitem"); // 저장된 대화 클릭 → 메시지 복원
  await page.waitForFunction(
    () => document.querySelectorAll(".work .row").length >= 2,
    null,
    { timeout: 15000 },
  );
  const restored = await page.locator(".work .row").count();
  console.log(`세션 저장소: ${convCount}개 대화 · 복원된 메시지 ${restored}개`);

  // 세션 삭제: 첫 항목 삭제 → 목록 개수 감소
  await page.locator(".convlist .convitem").first().locator(".convdel").click();
  await page.waitForFunction(
    (n) => document.querySelectorAll(".convlist .convitem").length < n,
    convCount,
    { timeout: 10000 },
  );
  const afterDel = await page.locator(".convlist .convitem").count();
  console.log(`삭제 후 대화: ${afterDel}개`);
  if (afterDel >= convCount) throw new Error("세션 삭제 미동작");

  if (!draft || draft.length < 5) throw new Error("IME 초벌이 안 뜸 (버그 미수정)");
  if (!trans || trans.length < 5) throw new Error("작업대 번역 없음");
  if (!cust || cust.length < 5) throw new Error("고객 화면 미반영");
  if (!inbound || inbound.length < 5) throw new Error("고객 입력 역번역 미동작");
  if (convCount < 1) throw new Error("대화가 저장소에 안 쌓임");
  if (restored < 2) throw new Error("저장된 대화 복원 실패");
  if (errors.length) throw new Error("콘솔 에러: " + errors.join(" | "));
  console.log("\nSMOKE PASS ✅  세션 저장소 + IME 초벌 + 양방향 번역 + 복원");
  await browser.close();
} catch (e) {
  console.error("SMOKE FAIL ❌", e.message);
  if (errors.length) console.error("errors:", errors);
  await browser.close();
  process.exit(1);
}
