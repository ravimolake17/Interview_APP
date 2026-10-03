import { companyDisplayName, companyLogoSrc, isKabelCompany } from './companyBranding';

const PAGE_WIDTH = 612;
const PAGE_HEIGHT = 792;
const MARGIN = 40;
const HEADER_HEIGHT = 78;
const FOOTER_HEIGHT = 28;
const ORANGE = '#f97316';
const SLATE = '#334155';
const MUTED = '#64748b';
const LINE = '#cbd5e1';
const HEADER_BG = '#f97316';
const ALT_ROW = '#fff7ed';
const WHITE = '#ffffff';
const BLACK = '#0f172a';

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function escapeCsv(value) {
  const text = value == null ? '' : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function pdfEscape(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)');
}

function toWinAnsi(value) {
  return String(value ?? '').replace(/[^\x20-\x7E]/g, (ch) => {
    const map = {
      '–': '-',
      '—': '-',
      '’': "'",
      '‘': "'",
      '“': '"',
      '”': '"',
      '•': '*',
      '…': '...',
    };
    return map[ch] || '?';
  });
}

function pdfColor(hex) {
  const n = parseInt(hex.replace('#', ''), 16);
  const r = ((n >> 16) & 255) / 255;
  const g = ((n >> 8) & 255) / 255;
  const b = (n & 255) / 255;
  return `${r.toFixed(3)} ${g.toFixed(3)} ${b.toFixed(3)}`;
}

let measureCtx;
function measureText(text, fontSize, bold = false) {
  if (!measureCtx) {
    measureCtx = document.createElement('canvas').getContext('2d');
  }
  measureCtx.font = `${bold ? 'bold ' : ''}${fontSize}px Helvetica, Arial, sans-serif`;
  return measureCtx.measureText(text).width;
}

function wrapText(text, maxWidth, fontSize, bold = false) {
  const source = toWinAnsi(text);
  if (!source.trim()) return [''];
  const words = source.split(/\s+/);
  const lines = [];
  let current = '';

  const fits = (value) => measureText(value, fontSize, bold) <= maxWidth;

  const splitLong = (word) => {
    let rest = word;
    while (rest) {
      let cut = rest.length;
      while (cut > 1 && !fits(rest.slice(0, cut))) cut -= 1;
      lines.push(rest.slice(0, cut));
      rest = rest.slice(cut);
    }
  };

  words.forEach((word) => {
    const trial = current ? `${current} ${word}` : word;
    if (fits(trial)) {
      current = trial;
      return;
    }
    if (current) lines.push(current);
    if (fits(word)) {
      current = word;
    } else {
      splitLong(word);
      current = '';
    }
  });
  if (current) lines.push(current);
  return lines.length ? lines : [''];
}

function buildSummaryRows(stats) {
  return [
    ['Metric', 'Value'],
    ['Total Candidates', stats.total_candidates ?? 0],
    ['Active Jobs', stats.active_jobs ?? 0],
    ['AI Screened', stats.ai_screened ?? 0],
    ['Needs Review', stats.pending_reviews ?? 0],
    ['Shortlisted', stats.shortlisted ?? 0],
    ['Interview Scheduled', stats.interview_scheduled ?? 0],
    ['Interview Completed', stats.interview_completed ?? 0],
    ['Rejected', stats.rejected ?? 0],
    ['Invite emails issued', stats.invite_delivery?.issued ?? 0],
    ['Shortlisted with no invite', stats.invite_delivery?.not_issued ?? 0],
    ['Shortlisted awaiting booking', stats.invite_delivery?.awaiting_booking ?? 0],
    ['Average Match Score (%)', stats.average_match_score ?? 0],
  ];
}

function inviteStatusLabel(candidate) {
  if (candidate.interviewCompleted || candidate.status === 'Interview Completed') return 'Completed';
  if (candidate.interviewScheduled || candidate.status === 'Interview Scheduled') return 'Booked';
  if (candidate.inviteSent) return 'Invite sent';
  if (candidate.canResendInvite || candidate.status === 'Shortlisted') return 'Not sent';
  return '—';
}

function buildCandidateRows(candidates) {
  return [
    ['Name', 'Email', 'Job', 'Match Score (%)', 'Status', 'Invite'],
    ...candidates.map((c) => [
      c.name,
      c.email,
      c.appliedJob,
      c.matchScore,
      c.status,
      inviteStatusLabel(c),
    ]),
  ];
}

function buildTableRows(title, headers, rows) {
  return { title, headers, rows };
}

function collectReportData(stats, candidates) {
  return {
    generatedAt: new Date().toLocaleString(),
    summary: buildSummaryRows(stats),
    statusDistribution: buildTableRows(
      'Status Distribution',
      ['Status', 'Count'],
      (stats.status_distribution || []).map((row) => [row.name, row.value]),
    ),
    applicationsPerJob: buildTableRows(
      'Applications by Job',
      ['Job', 'Applicants', 'Avg Score (%)'],
      (stats.applications_per_job || []).map((row) => [
        row.name,
        row.applicants,
        row.avgScore ?? '',
      ]),
    ),
    matchTrend: buildTableRows(
      'Match Score Trend',
      ['Month', 'Avg Score (%)', 'Screened'],
      (stats.match_trend || []).map((row) => [row.month, row.avgScore, row.screened ?? '']),
    ),
    topSkills: buildTableRows(
      'Top Skills',
      ['Skill', 'Candidates'],
      (stats.top_skills || []).map((row) => [row.skill, row.count]),
    ),
    hiringFunnel: buildTableRows(
      'Hiring Funnel',
      ['Stage', 'Count'],
      (stats.hiring_funnel || []).map((row) => [row.stage, row.count]),
    ),
    inviteDelivery: buildTableRows(
      'Interview Invite Emails',
      ['Name', 'Email', 'Job', 'Invite'],
      (stats.invite_delivery?.candidates || []).map((row) => [
        row.full_name,
        row.email,
        row.job_position || '',
        row.invite_sent ? 'Sent' : 'Not sent',
      ]),
    ),
    candidates: buildCandidateRows(candidates),
  };
}

function reportMeta(company) {
  const name = companyDisplayName(company);
  return {
    name,
    title: `${name} Recruitment Report`,
    footer: `${name} Recruitment  |  Confidential`,
    slug: isKabelCompany(company) ? 'rr-kabel-report' : 'rr-parkon-report',
  };
}

async function loadBrandAssets(company) {
  const img = new Image();
  const src = companyLogoSrc(company);
  img.src = src;
  const pngResponse = fetch(src);
  await img.decode();

  const maxPx = 420;
  const scale = Math.min(1, maxPx / Math.max(img.naturalWidth, 1));
  const width = Math.max(1, Math.round(img.naturalWidth * scale));
  const height = Math.max(1, Math.round(img.naturalHeight * scale));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);

  const { data } = ctx.getImageData(0, 0, width, height);
  const rgb = new Uint8Array(width * height * 3);
  for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
    const alpha = data[i + 3] / 255;
    rgb[j] = Math.round(data[i] * alpha + 255 * (1 - alpha));
    rgb[j + 1] = Math.round(data[i + 1] * alpha + 255 * (1 - alpha));
    rgb[j + 2] = Math.round(data[i + 2] * alpha + 255 * (1 - alpha));
  }

  let pngBytes = new Uint8Array();
  try {
    const response = await pngResponse;
    if (response.ok || response.status === 0) {
      pngBytes = new Uint8Array(await response.arrayBuffer());
    }
  } catch {
    pngBytes = new Uint8Array();
  }

  return {
    rgb,
    width,
    height,
    pngBytes,
    naturalWidth: img.naturalWidth,
    naturalHeight: img.naturalHeight,
  };
}

function ascii(text) {
  return new TextEncoder().encode(text);
}

function concatBytes(parts) {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  parts.forEach((part) => {
    out.set(part, offset);
    offset += part.length;
  });
  return out;
}

class ReportPdf {
  constructor(brand, generatedAt, reportTitle = 'Recruitment Report', reportFooter = 'Confidential') {
    this.brand = brand;
    this.generatedAt = generatedAt;
    this.reportTitle = reportTitle;
    this.reportFooter = reportFooter;
    this.pages = [];
    this.y = 0;
    this.contentWidth = PAGE_WIDTH - MARGIN * 2;
    this.contentTop = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT;
    this.contentBottom = MARGIN + FOOTER_HEIGHT;
    this.addPage();
  }

  addPage() {
    this.pages.push([]);
    this.y = this.contentTop;
    this.drawChrome();
  }

  op(command) {
    this.pages[this.pages.length - 1].push(command);
  }

  remaining() {
    return this.y - this.contentBottom;
  }

  ensureSpace(height) {
    if (this.remaining() < height) this.addPage();
  }

  rect(x, yBottom, w, h, { fill, stroke, lineWidth = 0.6 } = {}) {
    if (fill) this.op(`${pdfColor(fill)} rg`);
    if (stroke) {
      this.op(`${pdfColor(stroke)} RG`);
      this.op(`${lineWidth} w`);
    }
    this.op(`${x.toFixed(2)} ${yBottom.toFixed(2)} ${w.toFixed(2)} ${h.toFixed(2)} re`);
    if (fill && stroke) this.op('B');
    else if (fill) this.op('f');
    else this.op('S');
  }

  text(value, x, y, { size = 10, bold = false, color = BLACK } = {}) {
    const safe = pdfEscape(toWinAnsi(value));
    this.op(
      `BT /F${bold ? 2 : 1} ${size} Tf ${pdfColor(color)} rg ${x.toFixed(2)} ${y.toFixed(2)} Td (${safe}) Tj ET`,
    );
  }

  drawChrome() {
    const logoHeight = 36;
    const logoWidth = this.brand
      ? logoHeight * (this.brand.width / this.brand.height)
      : 0;
    const logoBottom = PAGE_HEIGHT - MARGIN - logoHeight;

    if (this.brand) {
      this.op('q');
      this.op(
        `${logoWidth.toFixed(2)} 0 0 ${logoHeight.toFixed(2)} ${MARGIN} ${logoBottom.toFixed(2)} cm /Im1 Do`,
      );
      this.op('Q');
    }

    const titleX = MARGIN + (this.brand ? logoWidth + 14 : 0);
    this.text(this.reportTitle, titleX, PAGE_HEIGHT - MARGIN - 18, {
      size: 14,
      bold: true,
      color: BLACK,
    });
    this.text(`Generated: ${this.generatedAt}`, titleX, PAGE_HEIGHT - MARGIN - 34, {
      size: 9,
      color: MUTED,
    });
    this.text('Hiring analytics from the live candidate database', titleX, PAGE_HEIGHT - MARGIN - 48, {
      size: 8,
      color: MUTED,
    });

    this.rect(MARGIN, this.contentTop + 10, this.contentWidth, 2.5, { fill: ORANGE });
  }

  sectionTitle(title) {
    this.ensureSpace(28);
    this.y -= 6;
    this.text(title, MARGIN, this.y - 12, { size: 12, bold: true, color: SLATE });
    this.y -= 20;
  }

  drawTable(title, headers, rows, colRatios) {
    if (!rows.length) return;
    const widths = colRatios.map((ratio) => ratio * this.contentWidth);
    const fontSize = 8;
    const headerSize = 8;
    const paddingX = 6;
    const paddingY = 5;
    const lineGap = 2;

    const wrapRow = (row, bold, size) => row.map((cell, index) => (
      wrapText(cell, Math.max(12, widths[index] - paddingX * 2), size, bold)
    ));

    const rowHeight = (lines) => {
      const count = Math.max(...lines.map((cell) => cell.length), 1);
      return Math.max(18, paddingY * 2 + count * (fontSize + lineGap));
    };

    const headerLines = wrapRow(headers, true, headerSize);
    const headerH = rowHeight(headerLines);
    this.ensureSpace(28 + headerH + 12);
    this.sectionTitle(title);

    const paintRow = (lines, height, { header = false, alt = false } = {}) => {
      const bottom = this.y - height;
      let x = MARGIN;
      lines.forEach((cellLines, index) => {
        const fill = header ? HEADER_BG : alt ? ALT_ROW : WHITE;
        this.rect(x, bottom, widths[index], height, { fill, stroke: LINE, lineWidth: 0.4 });
        let textY = this.y - paddingY - (header ? headerSize : fontSize) + 1;
        cellLines.forEach((line) => {
          this.text(line, x + paddingX, textY, {
            size: header ? headerSize : fontSize,
            bold: header,
            color: header ? WHITE : BLACK,
          });
          textY -= fontSize + lineGap;
        });
        x += widths[index];
      });
      this.y = bottom;
    };

    paintRow(headerLines, headerH, { header: true });

    rows.forEach((row, index) => {
      const lines = wrapRow(row, false, fontSize);
      const height = rowHeight(lines);
      if (this.remaining() < height) {
        this.addPage();
        this.sectionTitle(`${title} (continued)`);
        paintRow(headerLines, headerH, { header: true });
      }
      paintRow(lines, height, { alt: index % 2 === 1 });
    });

    this.y -= 10;
  }

  finalize() {
    const total = this.pages.length;
    this.pages.forEach((ops, index) => {
      const footerY = MARGIN + 10;
      ops.push(`${pdfColor(ORANGE)} rg`);
      ops.push(`${MARGIN} ${MARGIN + 22} ${this.contentWidth} 1.2 re f`);
      ops.push(
        `BT /F1 8 Tf ${pdfColor(MUTED)} rg ${MARGIN} ${footerY} Td (${pdfEscape(this.reportFooter)}) Tj ET`,
      );
      const label = `Page ${index + 1} of ${total}`;
      const labelX = PAGE_WIDTH - MARGIN - measureText(label, 8);
      ops.push(
        `BT /F1 8 Tf ${pdfColor(MUTED)} rg ${labelX.toFixed(2)} ${footerY} Td (${pdfEscape(label)}) Tj ET`,
      );
    });
  }

  toBlob(brand) {
    this.finalize();

    const objects = [];
    const add = (body) => {
      objects.push(typeof body === 'string' ? ascii(body) : body);
      return objects.length;
    };

    const fontRegular = add(ascii('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'));
    const fontBold = add(ascii('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>'));

    let imageId = null;
    if (brand) {
      const dict = ascii(
        `<< /Type /XObject /Subtype /Image /Width ${brand.width} /Height ${brand.height} ` +
          `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length ${brand.rgb.length} >>\nstream\n`,
      );
      const end = ascii('\nendstream');
      imageId = add(concatBytes([dict, brand.rgb, end]));
    }

    const pageIds = this.pages.map((ops) => {
      const stream = ascii(ops.join('\n'));
      const content = concatBytes([
        ascii(`<< /Length ${stream.length} >>\nstream\n`),
        stream,
        ascii('\nendstream'),
      ]);
      const contentId = add(content);
      const xobject = imageId ? `/XObject << /Im1 ${imageId} 0 R >>` : '';
      return add(ascii(
        `<< /Type /Page /Parent 0 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] ` +
          `/Resources << /Font << /F1 ${fontRegular} 0 R /F2 ${fontBold} 0 R >> ${xobject} >> ` +
          `/Contents ${contentId} 0 R >>`,
      ));
    });

    const pagesId = add(ascii(
      `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pageIds.length} >>`,
    ));

    const patched = objects.map((body, index) => {
      const id = index + 1;
      if (pageIds.includes(id)) {
        const text = new TextDecoder().decode(body).replace('/Parent 0 0 R', `/Parent ${pagesId} 0 R`);
        return ascii(text);
      }
      return body;
    });

    const catalogId = patched.length + 1;
    patched.push(ascii(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`));

    const chunks = [ascii('%PDF-1.4\n')];
    const offsets = [0];
    let cursor = chunks[0].length;

    patched.forEach((body, index) => {
      const header = ascii(`${index + 1} 0 obj\n`);
      const footer = ascii('\nendobj\n');
      offsets.push(cursor);
      chunks.push(header, body, footer);
      cursor += header.length + body.length + footer.length;
    });

    const xrefStart = cursor;
    let xref = `xref\n0 ${patched.length + 1}\n0000000000 65535 f \n`;
    offsets.slice(1).forEach((offset) => {
      xref += `${String(offset).padStart(10, '0')} 00000 n \n`;
    });
    xref += `trailer\n<< /Size ${patched.length + 1} /Root ${catalogId} 0 R >>\n`;
    xref += `startxref\n${xrefStart}\n%%EOF`;
    chunks.push(ascii(xref));

    return new Blob([concatBytes(chunks)], { type: 'application/pdf' });
  }
}

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let crc = i;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
    }
    table[i] = crc >>> 0;
  }
  return table;
})();

function crc32(data) {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc = CRC32_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function u16(value) {
  return new Uint8Array([value & 255, (value >>> 8) & 255]);
}

function u32(value) {
  return new Uint8Array([
    value & 255,
    (value >>> 8) & 255,
    (value >>> 16) & 255,
    (value >>> 24) & 255,
  ]);
}

function zipStore(files) {
  const locals = [];
  const centrals = [];
  let offset = 0;

  files.forEach((file) => {
    const nameBytes = ascii(file.name);
    const data = file.data;
    const crc = crc32(data);
    const local = concatBytes([
      u32(0x04034b50),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(data.length),
      u32(data.length),
      u16(nameBytes.length),
      u16(0),
      nameBytes,
      data,
    ]);
    const central = concatBytes([
      u32(0x02014b50),
      u16(20),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(data.length),
      u32(data.length),
      u16(nameBytes.length),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(0),
      u32(offset),
      nameBytes,
    ]);
    locals.push(local);
    centrals.push(central);
    offset += local.length;
  });

  const centralDir = concatBytes(centrals);
  const eocd = concatBytes([
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(files.length),
    u16(files.length),
    u32(centralDir.length),
    u32(offset),
    u16(0),
  ]);
  return concatBytes([...locals, centralDir, eocd]);
}

function colLetter(index) {
  let n = index + 1;
  let label = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    label = String.fromCharCode(65 + rem) + label;
    n = Math.floor((n - 1) / 26);
  }
  return label;
}

function cellRef(row, col) {
  return colLetter(col) + String(row);
}

function inlineCell(ref, value, style) {
  const text = escapeHtml(value == null ? '' : String(value));
  const styleAttr = style ? ' s="' + style + '"' : '';
  const numeric = typeof value === 'number' && Number.isFinite(value);
  if (numeric) {
    return '<c r="' + ref + '"' + styleAttr + '><v>' + value + '</v></c>';
  }
  return '<c r="' + ref + '" t="inlineStr"' + styleAttr + '><is><t>' + text + '</t></is></c>';
}

function xlsxStyles() {
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<fonts count="5">' +
    '<font><sz val="11"></sz><color theme="1"></color><name val="Calibri"></name></font>' +
    '<font><b></b><sz val="18"></sz><color rgb="FF0F172A"></color><name val="Calibri"></name></font>' +
    '<font><sz val="10"></sz><color rgb="FF64748B"></color><name val="Calibri"></name></font>' +
    '<font><b></b><sz val="11"></sz><color rgb="FFFFFFFF"></color><name val="Calibri"></name></font>' +
    '<font><b></b><sz val="13"></sz><color rgb="FFEA580C"></color><name val="Calibri"></name></font>' +
    '</fonts>' +
    '<fills count="4">' +
    '<fill><patternFill patternType="none"></patternFill></fill>' +
    '<fill><patternFill patternType="gray125"></patternFill></fill>' +
    '<fill><patternFill patternType="solid"><fgColor rgb="FFF97316"></fgColor></patternFill></fill>' +
    '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF7ED"></fgColor></patternFill></fill>' +
    '</fills>' +
    '<borders count="2">' +
    '<border><left></left><right></right><top></top><bottom></bottom></border>' +
    '<border>' +
    '<left style="thin"><color rgb="FFCBD5E1"></color></left>' +
    '<right style="thin"><color rgb="FFCBD5E1"></color></right>' +
    '<top style="thin"><color rgb="FFCBD5E1"></color></top>' +
    '<bottom style="thin"><color rgb="FFCBD5E1"></color></bottom>' +
    '</border>' +
    '</borders>' +
    '<cellXfs count="7">' +
    '<xf fontId="0" fillId="0" borderId="0"></xf>' +
    '<xf fontId="1" fillId="0" borderId="0" applyFont="1"></xf>' +
    '<xf fontId="2" fillId="0" borderId="0" applyFont="1"></xf>' +
    '<xf fontId="4" fillId="0" borderId="0" applyFont="1"></xf>' +
    '<xf fontId="3" fillId="2" borderId="1" applyFont="1" applyFill="1" applyBorder="1"></xf>' +
    '<xf fontId="0" fillId="0" borderId="1" applyBorder="1"></xf>' +
    '<xf fontId="0" fillId="3" borderId="1" applyFill="1" applyBorder="1"></xf>' +
    '</cellXfs>' +
    '</styleSheet>'
  );
}

function xlsxDrawing(widthPx, heightPx) {
  const cx = Math.round(widthPx * 9525);
  const cy = Math.round(heightPx * 9525);
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">' +
    '<xdr:oneCellAnchor editAs="oneCell">' +
    '<xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>' +
    '<xdr:ext cx="' + cx + '" cy="' + cy + '"></xdr:ext>' +
    '<xdr:pic>' +
    '<xdr:nvPicPr><xdr:cNvPr id="1" name="Parkon"></xdr:cNvPr><xdr:cNvPicPr><a:picLocks noChangeAspect="1"></a:picLocks></xdr:cNvPicPr></xdr:nvPicPr>' +
    '<xdr:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="rId1"></a:blip><a:stretch><a:fillRect></a:fillRect></a:stretch></xdr:blipFill>' +
    '<xdr:spPr><a:prstGeom prst="rect"><a:avLst></a:avLst></a:prstGeom></xdr:spPr>' +
    '</xdr:pic>' +
    '<xdr:clientData></xdr:clientData>' +
    '</xdr:oneCellAnchor>' +
    '</xdr:wsDr>'
  );
}

function buildSheetXml(data, hasLogo, reportTitle) {
  const rows = [];
  let rowNum = hasLogo ? 4 : 1;
  const pushRow = (cells, height) => {
    const ht = height ? ' ht="' + height + '" customHeight="1"' : '';
    rows.push('<row r="' + rowNum + '"' + ht + '>' + cells.join('') + '</row>');
    rowNum += 1;
  };

  if (hasLogo) {
    rows.push('<row r="1" ht="22" customHeight="1"></row>');
    rows.push('<row r="2" ht="22" customHeight="1"></row>');
    rows.push('<row r="3" ht="18" customHeight="1"></row>');
  }

  pushRow([inlineCell(cellRef(rowNum, 0), reportTitle || 'Recruitment Report', 1)]);
  pushRow([inlineCell(cellRef(rowNum, 0), 'Generated: ' + data.generatedAt, 2)]);
  pushRow([]);

  const writeTable = (title, headers, tableRows) => {
    if (!tableRows.length) return;
    pushRow([inlineCell(cellRef(rowNum, 0), title, 3)]);
    pushRow(headers.map((header, col) => inlineCell(cellRef(rowNum, col), header, 4)));
    tableRows.forEach((tableRow, index) => {
      const style = index % 2 === 1 ? 6 : 5;
      pushRow(tableRow.map((cell, col) => inlineCell(cellRef(rowNum, col), cell, style)));
    });
    pushRow([]);
  };

  writeTable('Summary', data.summary[0], data.summary.slice(1));
  [
    data.statusDistribution,
    data.applicationsPerJob,
    data.matchTrend,
    data.topSkills,
    data.hiringFunnel,
    data.inviteDelivery,
    { title: 'Candidates', headers: data.candidates[0], rows: data.candidates.slice(1) },
  ].forEach((section) => writeTable(section.title, section.headers, section.rows));

  const cols = (
    '<cols>' +
    '<col min="1" max="1" width="28" customWidth="1"></col>' +
    '<col min="2" max="2" width="36" customWidth="1"></col>' +
    '<col min="3" max="3" width="32" customWidth="1"></col>' +
    '<col min="4" max="4" width="18" customWidth="1"></col>' +
    '<col min="5" max="5" width="18" customWidth="1"></col>' +
    '<col min="6" max="6" width="16" customWidth="1"></col>' +
    '</cols>'
  );

  const drawing = hasLogo
    ? '<drawing xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1"></drawing>'
    : '';

  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
    cols +
    '<sheetData>' + rows.join('') + '</sheetData>' +
    drawing +
    '</worksheet>'
  );
}

function buildXlsx(data, brand, reportTitle) {
  const hasLogo = Boolean(brand?.pngBytes?.length);
  const files = [
    {
      name: '[Content_Types].xml',
      data: ascii(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"></Default>' +
          '<Default Extension="xml" ContentType="application/xml"></Default>' +
          '<Default Extension="png" ContentType="image/png"></Default>' +
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"></Override>' +
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"></Override>' +
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"></Override>' +
          (hasLogo
            ? '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"></Override>'
            : '') +
          '</Types>',
      ),
    },
    {
      name: '_rels/.rels',
      data: ascii(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"></Relationship>' +
          '</Relationships>',
      ),
    },
    {
      name: 'xl/workbook.xml',
      data: ascii(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
          '<sheets><sheet name="Report" sheetId="1" r:id="rId1"></sheet></sheets>' +
          '</workbook>',
      ),
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: ascii(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"></Relationship>' +
          '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"></Relationship>' +
          '</Relationships>',
      ),
    },
    { name: 'xl/styles.xml', data: ascii(xlsxStyles()) },
    { name: 'xl/worksheets/sheet1.xml', data: ascii(buildSheetXml(data, hasLogo, reportTitle)) },
  ];

  if (hasLogo) {
    const displayHeight = 48;
    const displayWidth = Math.round(
      displayHeight * (brand.naturalWidth / Math.max(brand.naturalHeight, 1)),
    );
    files.push(
      {
        name: 'xl/worksheets/_rels/sheet1.xml.rels',
        data: ascii(
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"></Relationship>' +
            '</Relationships>',
        ),
      },
      {
        name: 'xl/drawings/drawing1.xml',
        data: ascii(xlsxDrawing(displayWidth, displayHeight)),
      },
      {
        name: 'xl/drawings/_rels/drawing1.xml.rels',
        data: ascii(
          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"></Relationship>' +
            '</Relationships>',
        ),
      },
      { name: 'xl/media/image1.png', data: brand.pngBytes },
    );
  }

  return zipStore(files);
}

export function exportReportCsv(stats, candidates, company) {
  const data = collectReportData(stats, candidates);
  const meta = reportMeta(company);
  const lines = [];

  lines.push(meta.title);
  lines.push(`Generated,${escapeCsv(data.generatedAt)}`);
  lines.push('');

  lines.push('Summary');
  data.summary.forEach((row) => lines.push(row.map(escapeCsv).join(',')));
  lines.push('');

  [
    data.statusDistribution,
    data.applicationsPerJob,
    data.matchTrend,
    data.topSkills,
    data.hiringFunnel,
    data.inviteDelivery,
  ].forEach((section) => {
    lines.push(section.title);
    lines.push(section.headers.map(escapeCsv).join(','));
    section.rows.forEach((row) => lines.push(row.map(escapeCsv).join(',')));
    lines.push('');
  });

  lines.push('Candidates');
  data.candidates.forEach((row) => lines.push(row.map(escapeCsv).join(',')));

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  downloadBlob(blob, `${meta.slug}_${timestamp()}.csv`);
}

export async function exportReportExcel(stats, candidates, company) {
  const data = collectReportData(stats, candidates);
  const meta = reportMeta(company);
  const brand = await loadBrandAssets(company).catch(() => null);
  const bytes = buildXlsx(data, brand, meta.title);
  const blob = new Blob([bytes], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  downloadBlob(blob, `${meta.slug}_${timestamp()}.xlsx`);
}

export async function exportReportPdf(stats, candidates, company) {
  const data = collectReportData(stats, candidates);
  const meta = reportMeta(company);
  const brand = await loadBrandAssets(company).catch(() => null);
  const pdf = new ReportPdf(brand, data.generatedAt, meta.title, meta.footer);

  pdf.drawTable('Summary', data.summary[0], data.summary.slice(1), [0.72, 0.28]);

  [
    { section: data.statusDistribution, widths: [0.72, 0.28] },
    { section: data.applicationsPerJob, widths: [0.5, 0.25, 0.25] },
    { section: data.matchTrend, widths: [0.4, 0.3, 0.3] },
    { section: data.topSkills, widths: [0.72, 0.28] },
    { section: data.hiringFunnel, widths: [0.72, 0.28] },
    { section: data.inviteDelivery, widths: [0.22, 0.28, 0.28, 0.22] },
  ].forEach(({ section, widths }) => {
    if (section.rows.length) {
      pdf.drawTable(section.title, section.headers, section.rows, widths);
    }
  });

  if (data.candidates.length > 1) {
    if (pdf.remaining() < 160) pdf.addPage();
    pdf.drawTable(
      'Candidates',
      data.candidates[0],
      data.candidates.slice(1),
      [0.16, 0.22, 0.22, 0.1, 0.14, 0.16],
    );
  }

  downloadBlob(pdf.toBlob(brand), `${meta.slug}_${timestamp()}.pdf`);
}

export async function exportReport(format, stats, candidates, company) {
  switch (format) {
    case 'csv':
      exportReportCsv(stats, candidates, company);
      break;
    case 'xlsx':
      await exportReportExcel(stats, candidates, company);
      break;
    case 'pdf':
      await exportReportPdf(stats, candidates, company);
      break;
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }
}
