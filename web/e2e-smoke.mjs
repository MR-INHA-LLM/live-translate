// FE 브라우저 검증 — 새 디자인(레코드 카드·검증 4종), i18n, API Docs.
// 전체 스택(docker --profile gpu)이 떠 있어야 한다. SMOKE_URL로 대상 지정.
import { chromium } from "@playwright/test";

const URL = process.env.SMOKE_URL ?? "http://localhost:18090";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

async function imeType(text) {
  await page.evaluate((t) => {
    const ta = document.querySelector(".work textarea");
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
  for (const sel of [".col.store", ".col.work", ".col.customer"]) {
    await page.waitForSelector(sel, { timeout: 15000 });
  }
  await page.waitForSelector(".work textarea:not([disabled])", { timeout: 20000 });

  // 타겟 id 로 → 검증 4종(초벌/최종/역번역/확인) 모두 나오게
  await page.selectOption(".pair .sel", "id");
  await page.waitForTimeout(1500);

  await imeType("내일 오후 회의를 금요일로 옮겨 주세요");
  // 초벌 '내용'이 뜰 때까지(pending 아님) 대기 — 너무 빨리 보내면 초벌/확인이 비어버림
  await page.waitForFunction(
    () => {
      const el = document.querySelector(".draftprev");
      return el && el.querySelector(".lab") && !el.querySelector(".pendingline");
    },
    null,
    { timeout: 25000 },
  );
  await page.waitForTimeout(400);
  const draft = (await page.textContent(".draftprev"))?.replace(/\s+/g, " ").trim();

  await page.click(".send");
  const mine = page.locator(".work .row.mine").last();
  await mine.locator(".lane.qlt").waitFor({ timeout: 45000 });
  await page.waitForTimeout(600);

  const hasDraft = await mine.locator(".lane.draft").count();
  const finalTxt = (await mine.locator(".lane.qlt .v").textContent())?.trim();
  const hasRt = await mine.locator(".lane.rt").count();
  const hasWit = await mine.locator(".lane.wit").count();
  const alignN = await mine.locator(".rec .al").count();
  console.log("초벌 레인:", hasDraft, "· 최종:", finalTxt?.slice(0, 40));
  console.log("역번역 레인:", hasRt, "· 확인 레인:", hasWit, "· 정렬 스팬:", alignN);

  // 고객 입력 → theirs 레코드
  const beforeTheirs = await page.locator(".work .row.theirs").count();
  await page.fill(".customer .dfield", "Bisa kirim materinya?");
  await page.click(".dsend");
  await page.waitForFunction((n) => document.querySelectorAll(".work .row.theirs").length > n, beforeTheirs, { timeout: 40000 });

  // i18n: EN 토글 → 좌측 제목이 Sessions로
  await page.click(".uilang button:nth-child(2)");
  await page.waitForTimeout(200);
  const brandEn = (await page.textContent(".store .brand"))?.trim();

  // API Docs 버튼
  const docsHref = await page.getAttribute(".docsbtn", "href");

  console.log("i18n EN 제목:", brandEn, "· API Docs href:", docsHref);

  if (!draft || draft.length < 5) throw new Error("초벌 미표시");
  if (!hasDraft) throw new Error("초벌 레인 없음");
  if (!finalTxt || finalTxt.length < 5) throw new Error("최종 번역 없음");
  if (!hasRt) throw new Error("역번역 레인 없음");
  if (!hasWit) throw new Error("확인(witness) 레인 없음");
  if (alignN < 1) throw new Error("정렬 스팬 없음");
  if (brandEn !== "Sessions") throw new Error("i18n EN 전환 실패: " + brandEn);
  if (docsHref !== "/docs") throw new Error("API Docs href 오류: " + docsHref);
  if (errors.length) throw new Error("콘솔 에러: " + errors.join(" | "));
  console.log("\nSMOKE PASS ✅  새 디자인 + 검증 4종 + i18n + API Docs");
  await browser.close();
} catch (e) {
  console.error("SMOKE FAIL ❌", e.message);
  if (errors.length) console.error("errors:", errors);
  await browser.close();
  process.exit(1);
}
