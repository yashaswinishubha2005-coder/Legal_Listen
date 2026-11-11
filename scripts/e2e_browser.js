// Browser smoke test for the LegalListen website (Playwright + Chromium).
//   make serve            (in another terminal)
//   node scripts/e2e_browser.js [http://localhost:8000] [screenshot-dir]
// Runs one consultation per language, answers every question with the first option, opens the
// Case Graph, Facts, Laws and Consultation tabs and fails on any JavaScript error.
const { chromium } = require("playwright");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || null;
const CASES = [
  { lang: "en", text: "My father passed away last year. Now my uncle is trying to sell our family land without asking us. The registration is fixed for next week." },
  { lang: "kn", text: "ನಿನ್ನೆ ಪಕ್ಕದ ಮನೆಯವರು ಜಗಳ ಮಾಡಿ ನನಗೆ ಕೋಲಿನಿಂದ ಹೊಡೆದರು, ತಲೆಗೆ ಗಾಯ ಆಯ್ತು. ಇವತ್ತು ರಾತ್ರಿ ಮತ್ತೆ ಬರ್ತೀನಿ ಅಂದ್ರು." },
  { lang: "hi", text: "एक आदमी ने बैंक से होने का बहाना करके फ़ोन किया, क्यूआर कोड स्कैन करवाया और अभी अभी मेरे खाते से तीस हज़ार रुपये कट गए।" },
];

(async () => {
  const browser = await chromium.launch();
  let failed = false;
  for (const c of CASES) {
    const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(BASE + "/login");
    await page.click("#guest");                       // sign-in page: continue as guest
    await page.waitForSelector(".lang-pick button");
    await page.click(`.lang-pick button[data-lang="${c.lang}"]`);
    await page.click("#start");
    await page.waitForSelector(".msg.assistant");
    await page.fill("#input", c.text);
    await page.click("#send");
    await page.waitForFunction(() => document.querySelectorAll(".msg.assistant").length >= 2);
    let answered = 0;
    for (let i = 0; i < 25; i++) {
      await page.waitForFunction(() => !document.querySelector("#typing"));
      const chips = await page.$$("#chips .chip");
      if (chips.length <= 1) break;
      await chips[0].click();
      answered++;
    }
    await page.waitForFunction(() => !document.querySelector("#typing"));
    for (const tab of ["facts", "graph", "laws", "consult"]) {
      await page.click(`.tabs button[data-tab="${tab}"]`);
      if (tab === "consult") await page.waitForSelector("#c-refresh", { timeout: 20000 });
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/${c.lang}_${tab}.png` });
    }
    const laws = await page.$$eval("#tab-consult .law", (ls) => ls.length);
    const urgent = await page.$eval("#urgent", (u) => !u.hidden);
    const ok = errors.length === 0 && laws > 0 && answered > 0;
    console.log(`${c.lang}: answered ${answered} questions, ${laws} provisions, urgent banner=${urgent}, errors=${JSON.stringify(errors)} -> ${ok ? "OK" : "FAIL"}`);
    failed = failed || !ok;
    await page.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
