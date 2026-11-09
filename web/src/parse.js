/** Browser-only import; the file does not leave this tab. */

export const MAX_FILE_BYTES = 32 * 1024 * 1024;
const MAX_TEXT_CHARS = 8_000_000;
const MAX_SEGMENT_CHARS = 420;

function safelyText(s) {
  return String(s || '').replace(/\r\n?/g, '\n').replace(/\u0000/g, '').trim();
}

export function segmentsFromText(raw) {
  const text = safelyText(raw);
  if (!text) throw new Error('Không tìm thấy chữ trong tài liệu.');
  if (text.length > MAX_TEXT_CHARS) throw new Error('Tài liệu quá dài cho bản web. Hãy chia thành các phần nhỏ.');
  const paragraphs = text.split(/\n\s*\n|\n(?=#{1,6}\s)/u);
  const result = [];
  for (const paragraph of paragraphs) {
    const source = paragraph.trim();
    if (!source) continue;
    const heading = /^#{1,6}\s+/.test(source);
    if (source.length <= MAX_SEGMENT_CHARS || heading) {
      result.push({ source, translation: '', status: 'pending', heading });
      continue;
    }
    const clauses = source.match(/[^。！？!?；;]+[。！？!?；;]?\s*/gu) || [source];
    let chunk = '';
    for (const clause of clauses) {
      if (chunk && chunk.length + clause.length > MAX_SEGMENT_CHARS) {
        result.push({source:chunk.trim(),translation:'',status:'pending',heading:false});
        chunk='';
      }
      if (clause.length <= MAX_SEGMENT_CHARS) chunk += clause;
      else {
        for (let i=0;i<clause.length;i+=MAX_SEGMENT_CHARS) {
          if (chunk.trim()) result.push({source:chunk.trim(),translation:'',status:'pending',heading:false});
          chunk=clause.slice(i,i+MAX_SEGMENT_CHARS);
        }
      }
    }
    if (chunk.trim()) result.push({source:chunk.trim(),translation:'',status:'pending',heading:false});
  }
  if (!result.length) throw new Error('Tài liệu không có nội dung để dịch.');
  return result;
}

function htmlToText(html) {
  const dom = new DOMParser().parseFromString(html, 'text/html');
  for (const el of dom.querySelectorAll('script,style,iframe,template,nav')) el.remove();
  const elements = [...dom.body.querySelectorAll('h1,h2,h3,h4,p,li,blockquote')];
  if (!elements.length) return safelyText(dom.body.textContent);
  return elements.map(el => {
    const text = safelyText(el.textContent);
    return /^H[1-4]$/.test(el.tagName) ? '# '+text : text;
  }).filter(Boolean).join('\n\n');
}

function localAttr(node, tag) {
  if (!node) return [];
  return [...node.getElementsByTagName('*')].filter(n => n.localName === tag);
}
function normalizedEntry(base, relative) {
  const result=[];
  for (const part of (base + relative).split('/')) {
    if (!part || part==='.') continue;
    if (part==='..') result.pop();
    else result.push(part);
  }
  return result.join('/');
}

async function extractEpub(bytes) {
  const {default:JSZip}=await import('jszip');
  const zip = await JSZip.loadAsync(bytes);
  const container = zip.file('META-INF/container.xml');
  if (!container) throw new Error('Không tìm thấy cấu trúc EPUB.');
  const meta = new DOMParser().parseFromString(await container.async('text'),'application/xml');
  const root = localAttr(meta, 'rootfile')[0];
  if (!root) throw new Error('EPUB thiếu file mục lục nội bộ.');
  const opfPath = root.getAttribute('full-path');
  const opfFile = zip.file(opfPath);
  if (!opfFile) throw new Error('EPUB thiếu nội dung OPF.');
  const opf = new DOMParser().parseFromString(await opfFile.async('text'),'application/xml');
  const items = new Map(localAttr(opf, 'item').map(el => [el.getAttribute('id'), el.getAttribute('href')]));
  const prefix = opfPath.substring(0, opfPath.lastIndexOf('/')+1);
  const parts = [];
  const spine = localAttr(opf, 'itemref');
  if (!spine.length) throw new Error('EPUB không có danh sách chương.');
  for (const itemref of spine) {
    const href = items.get(itemref.getAttribute('idref'));
    if (!href) continue;
    const file = zip.file(normalizedEntry(prefix, decodeURIComponent(href.split('#')[0])));
    if (!file) continue;
    const content = await file.async('text');
    parts.push(htmlToText(content));
    if (parts.join('').length > MAX_TEXT_CHARS) throw new Error('EPUB quá dài cho bản web.');
  }
  return parts.filter(Boolean).join('\n\n');
}

async function extractPdf(bytes) {
  const pdfjsLib=await import('pdfjs-dist');
  const {default:workerURL}=await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
  pdfjsLib.GlobalWorkerOptions.workerSrc=workerURL;
  const doc = await pdfjsLib.getDocument({data: new Uint8Array(bytes)}).promise;
  if (doc.numPages > 900) throw new Error('PDF có hơn 900 trang. Hãy chia file thành các phần nhỏ.');
  const pages=[];
  try {
    for (let index=1; index<=doc.numPages; index++) {
      const page = await doc.getPage(index);
      const content = await page.getTextContent();
      const lines=[];
      let current='';
      for (const item of content.items) {
        if (typeof item.str !== 'string') continue;
        current += item.str;
        if (item.hasEOL) { lines.push(current); current=''; }
      }
      if (current) lines.push(current);
      pages.push(lines.join('\n'));
      if (pages.join('').length > MAX_TEXT_CHARS) throw new Error('PDF quá dài cho bản web.');
    }
  } finally { await doc.destroy(); }
  return pages.filter(Boolean).join('\n\n');
}

export async function extractFile(file) {
  if (!file || file.size > MAX_FILE_BYTES) throw new Error('Bản web nhận file tối đa 32 MB.');
  const ext = file.name.toLowerCase().split('.').pop();
  const bytes = await file.arrayBuffer();
  let raw;
  if (['txt','md','markdown','srt','vtt'].includes(ext)) {
    raw = new TextDecoder('utf-8').decode(bytes);
  } else if (['html','htm'].includes(ext)) {
    raw = htmlToText(new TextDecoder('utf-8').decode(bytes));
  } else if (ext === 'epub') {
    raw = await extractEpub(bytes);
  } else if (ext === 'pdf') {
    raw = await extractPdf(bytes);
    if (raw.replace(/\s/g,'').length < 20) throw new Error('PDF không có lớp chữ. File scan cần OCR trước.');
  } else if (ext === 'docx') {
    const {default:mammoth}=await import('mammoth');
    const response = await mammoth.convertToHtml({arrayBuffer:bytes});
    raw = htmlToText(response.value);
  } else {
    throw new Error('Định dạng chưa hỗ trợ. Hãy dùng EPUB, PDF, Word, TXT hoặc HTML.');
  }
  const segments = segmentsFromText(raw);
  return {id:crypto.randomUUID(),name:file.name,kind:ext,target:'vi',created:Date.now(),segments};
}

export function syntheticSample(target) {
  return {
    id:crypto.randomUUID(),name:'Ví dụ tiếng Trung',kind:'sample',target,created:Date.now(),
    segments:segmentsFromText(
      '# 一段示例\n\n'+
      '中国有许多不同的地方文化。成都以美食和悠闲的生活节奏闻名。\n\n'+
      '这篇短文只是演示翻译功能。原文共两段，不包含任何医学建议或真实研究数据。'
    )
  };
}
