
const escapeHTML = text => String(text||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stripHead = text => String(text||'').replace(/^#{1,6}\s+/, '');
const colophon = project => {
  const translated = project.segments.filter(s=>s.translation).length;
  const prefix=project.target==='en'?'Machine translation draft, not human-reviewed.':'Bản dịch máy chưa được người duyệt.';
  return prefix+' '+translated+'/'+project.segments.length+' '+(project.target==='en'?'passages translated.':'đoạn đã dịch.');
};
const trans = s=>s.translation || (s.source+' '+(s.translation?'':'[chưa dịch]'));

function fileName(project,ext) {
  const base=project.name.replace(/\.[^.]+$/,'').replace(/[^\p{L}\p{N}_-]/gu,'_').slice(0,70)||'sach';
  return base+'-'+project.target+'.'+ext;
}
function download(blob,name) {
  const uri=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=uri;a.download=name;
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(uri),1000);
}
const tinyCSS='body{font:18px/1.7 Georgia,serif;margin:5%;color:#222}h1{font-size:1.6rem}p{margin:0 0 1rem;white-space:pre-wrap}.original{font:15px/1.65 sans-serif;color:#667;margin-top:-.5rem;border-left:2px solid #ccc;padding-left:.8rem}.meta{font:12px sans-serif;color:#777;margin-bottom:2rem}';

function htmlContent(project,bilingual) {
  const body=project.segments.map(s=>{
    const vi=escapeHTML(stripHead(trans(s)));
    const zh=escapeHTML(stripHead(s.source));
    const tag=s.heading?'h2':'p';
    return '<'+tag+'>'+vi+'</'+tag+'>'+(bilingual?'<p class="original" lang="zh-Hans">'+zh+'</p>':'');
  }).join('\n');
  return body;
}
function standaloneHTML(project,bilingual) {
  const title=escapeHTML(project.name);
  return ['<!doctype html><html lang="'+project.target+'"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>'+title+'</title><style>'+tinyCSS+'</style></head><body>',
    '<h1>'+title+'</h1><div class="meta">'+escapeHTML(colophon(project))+'</div>',
    htmlContent(project,bilingual),'</body></html>'].join('');
}
function opfXML(project) {
  const title=escapeHTML(project.name);
  const id=escapeHTML(project.id);
  return ['<?xml version="1.0" encoding="utf-8"?>',
    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="'+project.target+'">',
    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
    '<dc:identifier id="bookid">urn:uuid:'+id+'</dc:identifier>',
    '<dc:title>'+title+'</dc:title><dc:language>'+project.target+'</dc:language>',
    '<meta property="dcterms:modified">'+new Date().toISOString().replace(/\.\d+Z$/,'Z')+'</meta>',
    '</metadata><manifest>',
    '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
    '<item id="main" href="main.xhtml" media-type="application/xhtml+xml"/></manifest>',
    '<spine><itemref idref="main"/></spine></package>'].join('');
}
async function makeEpub(project,bilingual) {
  const {default:JSZip}=await import('jszip');
  const zip=new JSZip();
  zip.file('mimetype','application/epub+zip',{compression:'STORE'});
  zip.file('META-INF/container.xml','<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>');
  zip.file('OEBPS/content.opf',opfXML(project));
  const title=escapeHTML(project.name);
  zip.file('OEBPS/nav.xhtml','<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="'+project.target+'"><head><title>'+title+'</title></head><body><nav epub:type="toc"><h1>Contents</h1><ol><li><a href="main.xhtml">'+title+'</a></li></ol></nav></body></html>');
  zip.file('OEBPS/main.xhtml','<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="'+project.target+'"><head><title>'+title+'</title></head><body><h1>'+title+'</h1><p>'+escapeHTML(colophon(project))+'</p>'+htmlContent(project,bilingual)+'</body></html>');
  return zip.generateAsync({type:'blob',mimeType:'application/epub+zip'});
}
async function makeDocx(project,bilingual) {
  const {Document,Packer,Paragraph,HeadingLevel}=await import('docx');
  const children=[
    new Paragraph({text:project.name,heading:HeadingLevel.TITLE}),
    new Paragraph({text:colophon(project)}),
    ...project.segments.flatMap(s=>{
      const out=[new Paragraph({text:stripHead(trans(s)),...(s.heading?{heading:HeadingLevel.HEADING_2}:{})})];
      if(bilingual)out.push(new Paragraph({text:stripHead(s.source)}));
      return out;
    })
  ];
  const doc = new Document({sections:[{children}]});
  return Packer.toBlob(doc);
}
export async function exportProject(project,kind,bilingual) {
  let blob;
  if(kind==='txt'){
    const lines=[project.name,colophon(project),''];
    for(const s of project.segments) {
      lines.push(trans(s));
      if(bilingual)lines.push(s.source);
      lines.push('');
    }
    blob=new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'});
  } else if (kind==='html') {
    blob=new Blob([standaloneHTML(project,true)],{type:'text/html;charset=utf-8'});
  } else if(kind==='docx'){
    blob=await makeDocx(project,bilingual);
  } else if(kind==='epub') {
    blob=await makeEpub(project,bilingual);
  } else throw new Error('Định dạng xuất chưa hỗ trợ');
  download(blob,fileName(project,kind));
  return blob;
}
