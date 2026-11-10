// Local report renderer; never attaches to the user's signed-in Chrome.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { pathToFileURL } = require('url');
let chromium;
for (const candidate of [process.env.PLAYWRIGHT_MODULE, 'playwright-core',
  path.join(os.homedir(), '.agents/skills/github-issue-tracker/scripts/node_modules/playwright-core')].filter(Boolean)) {
  try { chromium = require(candidate).chromium; break; }
  catch (error) { if (error.code !== 'MODULE_NOT_FOUND') throw error; }
}
if (!chromium) throw new Error('Install playwright-core or set PLAYWRIGHT_MODULE');
(async () => {
  const html = path.resolve(process.argv[2]);
  const output = path.resolve(process.argv[3]);
  fs.mkdirSync(path.dirname(output), {recursive:true});
  const temporary = output + '.' + process.pid + '.tmp';
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(html).href, {waitUntil:'load'});
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({path:temporary, printBackground:true, preferCSSPageSize:true, format:'A4'});
    const bytes = fs.readFileSync(temporary);
    if (bytes.length < 1000 || bytes.subarray(0,5).toString() !== '%PDF-') throw new Error('Invalid rendered PDF');
    fs.renameSync(temporary, output);
    console.log(JSON.stringify({pdf:output, size:bytes.length}));
  } finally {
    await browser.close();
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
})().catch(error => { console.error(error.message); process.exitCode=1; });
