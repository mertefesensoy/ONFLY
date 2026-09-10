// md2docx.js — converts the ONFLY Markdown subset to .docx (docx-js).
// Usage: node md2docx.js <in.md> <out.docx> <srs|summary> "<header text>"
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, AlignmentType, LevelFormat, Header, Footer,
  PageNumber, TableOfContents,
} = require('docx');

const [, , inPath, outPath, mode = 'srs', headerText = ''] = process.argv;
const SUMMARY = mode === 'summary';
const BLUE = '0F62FE', INK = '161616', GRAY = '525252', RULE = 'C6CEDB';
const FONT = 'Arial', MONO = 'Consolas';
const cfg = SUMMARY
  ? { body: 18, table: 17, code: 15, margin: 850, title: 40, h1: 22, h2: 20, h3: 19, after: 60, line: 250 }
  : { body: 20, table: 17, code: 15, margin: 1134, title: 52, h1: 30, h2: 24, h3: 21, after: 110, line: 276 };
const PAGE_W = 11906; // A4
const CONTENT_W = PAGE_W - 2 * cfg.margin;

// ---------- inline formatting ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+?\*\*|`[^`]+?`|\*[^*\s][^*]*?\*)/g;
  let last = 0, m;
  const push = (t, extra) => { if (t) out.push(new TextRun({ text: t, font: FONT, ...base, ...extra })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index), {});
    const t = m[0];
    if (t.startsWith('**')) push(t.slice(2, -2), { bold: true });
    else if (t.startsWith('`')) push(t.slice(1, -1), { font: MONO });
    else push(t.slice(1, -1), { italics: true });
    last = m.index + t.length;
  }
  push(text.slice(last), {});
  return out;
}

// ---------- tables ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const borders = { top: border, bottom: border, left: border, right: border };
function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(s => s.trim());
}
function buildTable(lines) {
  const rows = lines.filter(l => !/^\|\s*:?-{2,}/.test(l.trim())).map(splitRow);
  const nCols = Math.max(...rows.map(r => r.length));
  rows.forEach(r => { while (r.length < nCols) r.push(''); });
  // width heuristic: proportional to content, but never narrower than the longest word
  const weights = [], mins = [];
  for (let c = 0; c < nCols; c++) {
    const plain = rows.map(r => r[c].replace(/[*`]/g, ''));
    const lens = plain.map(t => t.length);
    const avg = lens.reduce((a, b) => a + b, 0) / lens.length;
    const max = Math.max(...lens);
    weights.push(Math.min(Math.max(avg * 0.6 + max * 0.4, 4), 70));
    const longestTok = Math.max(...plain.map(t => Math.max(0, ...t.split(/\s+/).map(w => w.length))));
    mins.push(Math.min(Math.max(longestTok * 118 + 260, 600), 3200));
  }
  let minSum = mins.reduce((a, b) => a + b, 0);
  if (minSum > CONTENT_W) { const k = CONTENT_W / minSum; for (let c = 0; c < nCols; c++) mins[c] = Math.floor(mins[c] * k); }
  let widths = new Array(nCols).fill(0), fixed = new Array(nCols).fill(false);
  for (let iter = 0; iter < nCols + 1; iter++) {
    const freeW = CONTENT_W - widths.reduce((a, b, c) => a + (fixed[c] ? b : 0), 0);
    const freeWeight = weights.reduce((a, w, c) => a + (fixed[c] ? 0 : w), 0);
    let changed = false;
    for (let c = 0; c < nCols; c++) if (!fixed[c]) {
      widths[c] = Math.floor(freeW * weights[c] / freeWeight);
      if (widths[c] < mins[c]) { widths[c] = mins[c]; fixed[c] = true; changed = true; }
    }
    if (!changed) break;
  }
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);

  const tRows = rows.map((r, ri) => new TableRow({
    tableHeader: ri === 0,
    children: r.map((cell, ci) => new TableCell({
      borders,
      width: { size: widths[ci], type: WidthType.DXA },
      shading: ri === 0 ? { fill: 'E8EEFB', type: ShadingType.CLEAR, color: 'auto' } : undefined,
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      children: [new Paragraph({
        spacing: { after: 0, line: 240 },
        children: runs(cell, { size: cfg.table, bold: ri === 0 ? true : undefined, color: INK }),
      })],
    })),
  }));
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, rows: tRows });
}

// ---------- document body ----------
const src = fs.readFileSync(inPath, 'utf8').replace(/\r/g, '').split('\n');
const body = [];
let numLists = 0;
const numberingConfigs = [{
  reference: 'bullets',
  levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 460, hanging: 260 } } } }],
}];
let tocInserted = false, firstH1 = true;

function spacer() { body.push(new Paragraph({ spacing: { after: SUMMARY ? 40 : 80 }, children: [] })); }

for (let i = 0; i < src.length; i++) {
  const line = src[i];
  if (!line.trim()) continue;

  if (line.startsWith('```')) {
    const code = [];
    for (i++; i < src.length && !src[i].startsWith('```'); i++) code.push(src[i]);
    code.forEach((c, idx) => body.push(new Paragraph({
      spacing: { after: 0, before: idx === 0 ? 60 : 0, line: 228 },
      shading: { fill: 'F4F4F4', type: ShadingType.CLEAR, color: 'auto' },
      indent: { left: 120, right: 120 },
      children: [new TextRun({ text: c.length ? c : ' ', font: MONO, size: cfg.code, color: INK })],
    })));
    spacer();
    continue;
  }

  if (line.startsWith('|')) {
    const tl = [];
    while (i < src.length && src[i].startsWith('|')) tl.push(src[i++]);
    i--;
    body.push(buildTable(tl));
    spacer();
    continue;
  }

  if (line.startsWith('# ')) {
    body.push(new Paragraph({
      spacing: { before: SUMMARY ? 0 : 1800, after: 120 },
      children: [new TextRun({ text: line.slice(2), font: FONT, bold: true, size: cfg.title, color: INK })],
    }));
    continue;
  }

  if (line.startsWith('## ')) {
    if (!SUMMARY && !tocInserted) {
      body.push(new Paragraph({ pageBreakBefore: true, spacing: { after: 200 },
        children: [new TextRun({ text: 'Contents', font: FONT, bold: true, size: cfg.h1, color: BLUE })] }));
      src.forEach(l => {
        if (l.startsWith('## ')) body.push(new Paragraph({ spacing: { before: 70, after: 10 },
          children: [new TextRun({ text: l.slice(3), font: FONT, bold: true, size: 19, color: INK })] }));
        else if (l.startsWith('### ')) body.push(new Paragraph({ spacing: { after: 0 }, indent: { left: 380 },
          children: [new TextRun({ text: l.slice(4), font: FONT, size: 17, color: GRAY })] }));
      });
      tocInserted = true;
    }
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: !SUMMARY,
      children: [new TextRun({ text: line.slice(3), font: FONT })] }));
    firstH1 = false;
    continue;
  }
  if (line.startsWith('### ')) {
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: line.slice(4), font: FONT })] }));
    continue;
  }
  if (line.startsWith('#### ')) {
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: line.slice(5), font: FONT })] }));
    continue;
  }

  if (line.startsWith('> ')) {
    const q = [];
    while (i < src.length && src[i].startsWith('>')) q.push(src[i++].replace(/^>\s?/, ''));
    i--;
    body.push(new Paragraph({
      spacing: { before: 60, after: cfg.after + 40, line: cfg.line },
      indent: { left: 200, right: 200 },
      border: { left: { style: BorderStyle.SINGLE, size: 18, color: BLUE, space: 8 } },
      shading: { fill: 'F2F6FE', type: ShadingType.CLEAR, color: 'auto' },
      children: runs(q.join(' '), { size: cfg.body, color: INK }),
    }));
    continue;
  }

  if (/^- /.test(line)) {
    while (i < src.length && /^- /.test(src[i])) {
      body.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 },
        spacing: { after: SUMMARY ? 30 : 60, line: cfg.line },
        children: runs(src[i].slice(2), { size: cfg.body, color: INK }) }));
      i++;
    }
    i--;
    spacer();
    continue;
  }

  if (/^\d+\. /.test(line)) {
    const ref = `num${numLists++}`;
    numberingConfigs.push({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.',
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 300 } } } }] });
    while (i < src.length && /^\d+\. /.test(src[i])) {
      body.push(new Paragraph({ numbering: { reference: ref, level: 0 },
        spacing: { after: SUMMARY ? 30 : 60, line: cfg.line },
        children: runs(src[i].replace(/^\d+\.\s+/, ''), { size: cfg.body, color: INK }) }));
      i++;
    }
    i--;
    spacer();
    continue;
  }

  // plain paragraph: join consecutive text lines
  const para = [line];
  while (i + 1 < src.length && src[i + 1].trim() && !/^(#|\||>|- |\d+\. |```)/.test(src[i + 1])) para.push(src[++i]);
  body.push(new Paragraph({ spacing: { after: cfg.after, line: cfg.line },
    children: runs(para.join(' '), { size: cfg.body, color: INK }) }));
}

const headerFooter = SUMMARY ? {} : {
  headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
    children: [new TextRun({ text: headerText, font: FONT, size: 16, color: GRAY })] })] }) },
  footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: 'Page ', font: FONT, size: 16, color: GRAY }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: GRAY }),
      new TextRun({ text: ' of ', font: FONT, size: 16, color: GRAY }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: GRAY }),
    ] })] }) },
};

const doc = new Document({
  creator: 'Mert Efe Şensoy',
  title: SUMMARY ? 'ONFLY — Summary' : 'ONFLY — Software Requirements Specification',
  
  styles: {
    default: { document: { run: { font: FONT, size: cfg.body, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: cfg.h1, bold: true, font: FONT, color: BLUE },
        paragraph: { spacing: { before: SUMMARY ? 140 : 0, after: SUMMARY ? 50 : 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: cfg.h2, bold: true, font: FONT, color: INK },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: cfg.h3, bold: true, font: FONT, color: GRAY },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: numberingConfigs },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 },
      margin: { top: cfg.margin, bottom: cfg.margin, left: cfg.margin, right: cfg.margin } } },
    ...headerFooter,
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(outPath, buf); console.log('wrote', outPath); });
