/*
  Tablo -> yazdirilabilir sayfa (tarayicinin "PDF olarak kaydet"i ile PDF).
  Ekrandaki kolonlar ve satirlar aynen basilir; ust bilgide donem, filtreler
  ve uretim zamani yazar ki PDF baskasina iletildiginde baglam kaybolmasin.
*/
const esc = (v: unknown) => String(v ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))

export interface PrintCol { label: string; right?: boolean }

export function printTable(o: {
  title: string; company?: string; lines: string[]; cols: PrintCol[]; rows: string[][]; totals?: string[] | null; note?: string
}) {
  // Acilir pencere yerine gizli iframe: acilir pencere engeli olan tarayicilarda da calisir
  document.getElementById('tg-yazdir')?.remove()
  const fr = document.createElement('iframe')
  fr.id = 'tg-yazdir'
  fr.setAttribute('aria-hidden', 'true')
  Object.assign(fr.style, { position: 'fixed', right: '0', bottom: '0', width: '0', height: '0', border: '0' })
  document.body.appendChild(fr)
  const w = fr.contentWindow
  if (!w) return
  const th = o.cols.map((c) => `<th${c.right ? ' class="r"' : ''}>${esc(c.label)}</th>`).join('')
  const tr = (cells: string[], cls = '') => `<tr${cls ? ` class="${cls}"` : ''}>${cells.map((v, i) => `<td${o.cols[i]?.right ? ' class="r"' : ''}>${esc(v)}</td>`).join('')}</tr>`
  const zaman = new Date().toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: 'short' })
  w.document.write(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>${esc(o.title)}</title>
<style>
  @page { size: A4 landscape; margin: 12mm; }
  * { box-sizing: border-box }
  body { font: 10.5px/1.4 "Segoe UI", Arial, sans-serif; color: #0f1716; margin: 0 }
  header { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #0b0f0e; padding-bottom: 8px; margin-bottom: 10px }
  h1 { font-size: 17px; margin: 0 0 3px; letter-spacing: -.01em }
  .meta { color: #4a5856 } .brand { text-align: right; color: #4a5856 } .brand b { color: #0b0f0e }
  .brand i { display: inline-block; width: 8px; height: 8px; background: #1fc8b6; margin-right: 5px; transform: skewX(-17deg) }
  table { width: 100%; border-collapse: collapse }
  th { text-align: left; font-weight: 600; background: #f1f5f4; border-bottom: 1px solid #c9d3d1; padding: 5px 6px; white-space: nowrap }
  td { padding: 4px 6px; border-bottom: 1px solid #e2e8e7; vertical-align: top }
  .r { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
  tr.top td { font-weight: 700; border-top: 1.5px solid #0b0f0e; background: #f7f9f9 }
  thead { display: table-header-group } tr { break-inside: avoid }
  footer { margin-top: 8px; color: #7a8886; font-size: 9.5px }
</style></head><body>
<header><div><h1>${esc(o.title)}</h1>${o.lines.map((l) => `<div class="meta">${esc(l)}</div>`).join('')}</div>
<div class="brand"><div><i></i><b>Tailglass</b> Analytics</div>${o.company ? `<div>${esc(o.company)}</div>` : ''}<div>${esc(zaman)}</div></div></header>
<table><thead><tr>${th}</tr></thead><tbody>${o.rows.map((r) => tr(r)).join('')}${o.totals ? tr(o.totals, 'top') : ''}</tbody></table>
<footer>${esc(o.note || `${o.rows.length.toLocaleString('tr-TR')} satır.`)} Maliyet ve kâr FIFO yöntemiyle tahminidir.</footer>
</body></html>`)
  w.document.close()
  setTimeout(() => { w.focus(); w.print() }, 300)
}
