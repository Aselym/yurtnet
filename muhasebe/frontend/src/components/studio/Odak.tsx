import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowUp, Download, ImageDown, Search, SlidersHorizontal } from 'lucide-react'
import { api, download, type ColType, type QueryResult } from '../../lib/api'
import { fmt, fmtPeriodKey, fmtShort, isNum, rangeLabel } from '../../lib/format'
import type { Cumle } from '../../lib/yorum'
import { BarChart, LineChart, SERIES } from '../charts/Charts'
import { cn, inputCls } from '../ui'
import { ZAMAN_BOYUTLARI } from './bloklar'
import { grafikPng } from './Kart'
import { istek, kartAraligi, kartBasligi, olcuBlok, oncekiDonem, type Kart, type Pano } from './model'

/** Odak gorunumunde gosterilen ek olculer (kartin kendi olcusu her zaman ilk sirada). */
const EK = {
  SATIS_NET: ['net_tl', 'profit_tl', 'margin', 'qty', 'invoices', 'clients'],
  ALIS_NET: ['net_tl', 'qty', 'invoices'],
} as Record<string, string[]>

const OLCU_AD: Record<string, [string, ColType]> = {
  net_tl: ['Tutar', 'tl'], net_usd: ['Tutar $', 'usd'], profit_tl: ['Brüt kâr', 'tl'], margin: ['Kâr marjı', 'pct'],
  qty: ['Adet', 'num'], invoices: ['Fatura', 'num'], clients: ['Müşteri', 'num'], stock_age: ['Bekleme (gün)', 'num'],
}

type Sutun = { key: string; ad: string; tip: ColType; sayi: boolean }

export function OdakGorunum({ k, p, etiket, cumleler, onKapat, onDuzenle, duzenleAcik, kapsayici }: {
  k: Kart; p: Pano; etiket: (d: string) => string; cumleler: Cumle[]; onKapat: () => void
  onDuzenle: () => void; duzenleAcik: boolean; kapsayici?: string
}) {
  const b = olcuBlok(k)
  const yon = b.yon ?? 'SATIS_NET'
  const ana = b.olcu!
  const tip = (b.tip ?? 'num') as ColType
  const olculer = useMemo(() => [ana, ...(EK[yon] ?? []).filter((o) => o !== ana)], [ana, yon])
  const zaman = !!k.boyut && ZAMAN_BOYUTLARI.has(k.boyut)
  const karsilastir = !(k.seri && (zaman || ZAMAN_BOYUTLARI.has(k.seri)))   // donem anahtarlari donemler arasi eslesmez
  const ar = kartAraligi(k, p)
  const baslik = kartBasligi(k, etiket)
  const temelIstek = useMemo(() => ({ ...istek(k, p), measures: olculer, limit: 0 }), [k, p, olculer])
  const [veri, setVeri] = useState<{ sonuc: QueryResult; onceki: QueryResult } | null>(null)
  const [hata, setHata] = useState<string | null>(null)
  const [ara, setAra] = useState('')
  const [sira, setSira] = useState<{ key: string; desc: boolean }>({ key: zaman ? 'd0' : `m_${ana}`, desc: !zaman })
  const grafikKutu = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let iptal = false
    setHata(null)
    const [of, ot] = oncekiDonem(ar.from, ar.to)
    Promise.all([
      api.post<QueryResult>('/api/analiz/sorgu', temelIstek),
      api.post<QueryResult>('/api/analiz/sorgu', { ...temelIstek, date_from: of, date_to: ot }),
    ]).then(([sonuc, onceki]) => { if (!iptal) setVeri({ sonuc, onceki }) })
      .catch((e) => { if (!iptal) setHata(e instanceof Error ? e.message : 'Yüklenemedi') })
    return () => { iptal = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(temelIstek)])

  const mk = `m_${ana}`
  const anahtar = (r: Record<string, unknown>) => `${r.d0}|${r.d1 ?? ''}`
  const satirlar = useMemo(() => {
    if (!veri) return []
    const once = new Map(veri.onceki.rows.map((r) => [anahtar(r), r]))
    const zamanSirali = zaman ? [...veri.sonuc.rows].sort((a, c) => String(a.d0).localeCompare(String(c.d0))) : veri.sonuc.rows
    const toplam = Math.abs(Number(veri.sonuc.totals[mk]) || 0)
    return zamanSirali.map((r, i) => {
      // zaman kiriliminda "bir onceki donem" = bir onceki satir; digerlerinde ayni kalem, onceki esit donem
      const o = zaman ? (k.seri ? undefined : zamanSirali[i - 1]) : once.get(anahtar(r))
      const v = Number(r[mk]), ov = o ? Number(o[mk]) : NaN
      return {
        ...r,
        _pay: tip !== 'pct' && toplam ? (100 * v) / toplam : null,
        _onceki: isNum(ov) ? ov : null,
        _degisim: isNum(ov) && ov !== 0 ? (tip === 'pct' ? v - ov : (100 * (v - ov)) / Math.abs(ov)) : null,
        _etiket: `${fmtPeriodKey(r.d0, k.boyut)}${k.seri ? ` · ${fmtPeriodKey(r.d1, k.seri)}` : ''}`,
      } as Record<string, unknown>
    })
  }, [veri, zaman, k.seri, k.boyut, mk, tip])

  const gorunen = useMemo(() => {
    const q = ara.trim().toLocaleLowerCase('tr')
    const s = q ? satirlar.filter((r) => String(r._etiket).toLocaleLowerCase('tr').includes(q)) : [...satirlar]
    const ks = sira.key === 'd0' ? '_etiket' : sira.key
    s.sort((a, c) => {
      const x = a[ks], y = c[ks]
      const fark = typeof x === 'number' || typeof y === 'number'
        ? (Number(x ?? -Infinity) - Number(y ?? -Infinity)) : String(x).localeCompare(String(y), 'tr')
      return sira.desc ? -fark : fark
    })
    return s
  }, [satirlar, ara, sira])

  // grafik verisi: zaman = tum donemler; kategori = ilk 15. Ikinci kirilimda ilk 5 seri + Diger
  const grafik = useMemo(() => {
    if (!veri || !k.boyut) return null
    if (!k.seri) {
      const s = zaman ? satirlar : [...satirlar].sort((a, c) => Number(c[mk]) - Number(a[mk])).slice(0, 15)
      return { satirlar: s, seriler: [{ key: mk, label: b.ad, color: 'var(--rev-product)' }] }
    }
    const top = new Map<string, number>()
    for (const r of veri.sonuc.rows) top.set(String(r.d1), (top.get(String(r.d1)) || 0) + (Number(r[mk]) || 0))
    const ust5 = [...top.entries()].sort((a, c) => c[1] - a[1]).slice(0, 5).map(([x]) => x)
    const m = new Map<string, Record<string, unknown>>()
    for (const r of veri.sonuc.rows) {
      const x = String(r.d0), s = m.get(x) ?? { d0: x }, a = ust5.includes(String(r.d1)) ? `s::${r.d1}` : 's::Diğer'
      s[a] = (Number(s[a]) || 0) + (Number(r[mk]) || 0); m.set(x, s)
    }
    const ser = [...ust5.map((x) => `s::${x}`), ...(top.size > 5 ? ['s::Diğer'] : [])]
    let rows = [...m.values()]
    rows = zaman ? rows.sort((a, c) => String(a.d0).localeCompare(String(c.d0)))
      : rows.sort((a, c) => ser.reduce((t, x) => t + (Number(c[x]) || 0), 0) - ser.reduce((t, x) => t + (Number(a[x]) || 0), 0)).slice(0, 15)
    return { satirlar: rows, seriler: ser.map((x, i) => ({ key: x, label: x === 's::Diğer' ? 'Diğer' : fmtPeriodKey(x.slice(3), k.seri), color: SERIES[i] })) }
  }, [veri, satirlar, k.boyut, k.seri, zaman, mk, b.ad])

  const toplam = veri?.sonuc.totals[mk], onceki = veri?.onceki.totals[mk]
  const degisim = isNum(toplam) && isNum(onceki) && onceki !== 0 ? (tip === 'pct' ? toplam - onceki : (100 * (toplam - onceki)) / Math.abs(onceki)) : null
  const enYuksek = satirlar.length ? satirlar.reduce((a, c) => (Number(c[mk]) > Number(a[mk]) ? c : a)) : null
  const enDusuk = satirlar.length > 1 ? satirlar.reduce((a, c) => (Number(c[mk]) < Number(a[mk]) ? c : a)) : null

  const sutunlar: Sutun[] = [
    { key: mk, ad: OLCU_AD[ana]?.[0] === 'Tutar' ? b.ad : (OLCU_AD[ana]?.[0] ?? b.ad), tip, sayi: true },
    ...(tip !== 'pct' ? [{ key: '_pay', ad: 'Pay', tip: 'pct' as ColType, sayi: true }] : []),
    ...(karsilastir ? [
      { key: '_onceki', ad: zaman ? 'Bir önceki dönem' : 'Önceki eşit dönem', tip, sayi: true },
      { key: '_degisim', ad: tip === 'pct' ? 'Fark (puan)' : 'Değişim', tip: 'pct' as ColType, sayi: true }] : []),
    ...olculer.slice(1).map((o) => ({ key: `m_${o}`, ad: o === 'net_tl' ? (yon === 'ALIS_NET' ? 'Alış' : 'Satış') : OLCU_AD[o]?.[0] ?? o, tip: OLCU_AD[o]?.[1] ?? 'num', sayi: true })),
  ]

  const excel = () => download('/api/export/sorgu', { request: temelIstek, title: baslik, filename: baslik }).catch(() => {})
  const png = () => grafikPng(grafikKutu.current, baslik)

  return (
    <div className={cn('flex min-h-full flex-col gap-4', kapsayici)}>
      <div className="flex flex-wrap items-start gap-3">
        <button onClick={onKapat} className="inline-flex h-9 items-center gap-1.5 border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:bg-surface-2 rounded-[var(--radius-ctl)]">
          <ArrowLeft className="size-4" />Panoya dön
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="display text-[22px] leading-tight font-semibold text-ink first-letter:uppercase">{baslik}</h2>
          <p className="mt-0.5 text-[13px] text-muted">
            {rangeLabel(ar.from, ar.to)} · karşılaştırma: {rangeLabel(...oncekiDonem(ar.from, ar.to))}
            {Object.entries(k.filtre).filter(([, v]) => v.length).map(([d, v]) => ` · ${etiket(d)}: ${v.length > 3 ? `${v.length} seçim` : v.join(', ')}`).join('')}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={onDuzenle} aria-pressed={duzenleAcik}
            className={cn('inline-flex h-9 items-center gap-1.5 border px-3 text-[13px] rounded-[var(--radius-ctl)]', duzenleAcik ? 'border-ink bg-ink text-surface' : 'border-line text-ink-2 hover:text-ink')}>
            <SlidersHorizontal className="size-4" />Kartı düzenle
          </button>
          {k.boyut && <button onClick={png} className="inline-flex h-9 items-center gap-1.5 border border-line px-3 text-[13px] text-ink-2 hover:text-ink rounded-[var(--radius-ctl)]"><ImageDown className="size-4" />Görsel</button>}
          <button onClick={excel} className="inline-flex h-9 items-center gap-1.5 border border-line px-3 text-[13px] text-ink-2 hover:text-ink rounded-[var(--radius-ctl)]"><Download className="size-4" />Excel</button>
        </div>
      </div>

      {hata && <p className="panel p-6 text-center text-[13px] text-neg">{hata}</p>}

      {/* ozet */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Özet">
        <Kutu ad={b.ad} deger={fmtShort(toplam, tip)} alt={tip !== 'pct' && tip !== 'num' ? fmt(toplam, tip) : undefined} />
        <Kutu ad="Önceki eşit dönem" deger={fmtShort(onceki, tip)}
          alt={degisim !== null ? <span className={degisim >= 0 ? 'text-pos' : 'text-neg'}>{degisim >= 0 ? '↑' : '↓'} {tip === 'pct' ? `${Math.abs(degisim).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} puan` : `%${Math.abs(degisim).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}`}</span> : undefined} />
        <Kutu ad={k.boyut ? `En yüksek ${etiket(k.boyut).toLocaleLowerCase('tr')}` : 'Kalem sayısı'}
          deger={enYuksek ? fmtShort(enYuksek[mk], tip) : '—'} alt={enYuksek ? String(enYuksek._etiket) : undefined} />
        <Kutu ad={k.boyut ? `${(veri?.sonuc.row_count ?? 0).toLocaleString('tr-TR')} kalem · en düşük` : ''} deger={enDusuk ? fmtShort(enDusuk[mk], tip) : '—'}
          alt={enDusuk ? String(enDusuk._etiket) : undefined} />
      </section>

      {/* grafik */}
      {grafik && grafik.satirlar.length > 0 && (
        <section className="panel px-4 pt-4 pb-3" ref={grafikKutu}>
          <p className="mb-2 text-[12.5px] text-muted">{zaman ? 'Tüm dönemler' : `En büyük ${Math.min(15, grafik.satirlar.length)} kalem`}</p>
          {zaman && k.grafik === 'cizgi'
            ? <LineChart data={grafik.satirlar} xKey="d0" dim={k.boyut} type={tip} height={360} series={grafik.seriler} />
            : <BarChart data={grafik.satirlar} xKey="d0" dim={k.boyut} type={tip} height={360} series={grafik.seriler} />}
          {grafik.seriler.length > 1 && (
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2">
              {grafik.seriler.map((s) => <span key={s.key} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-[2px]" style={{ background: s.color }} />{s.label}</span>)}
            </div>
          )}
        </section>
      )}

      {/* yorum */}
      {cumleler.length > 0 && (
        <section className="panel px-5 py-4">
          <h3 className="text-[13.5px] font-semibold text-ink">Bu analiz ne söylüyor?</h3>
          <ul className="mt-2 space-y-1.5">
            {cumleler.map((c, i) => <li key={i} className="border-l-2 border-line-strong pl-2.5 text-[13.5px] leading-relaxed text-ink-2">{c.metin}</li>)}
          </ul>
        </section>
      )}

      {/* tablo */}
      {k.boyut && (
        <section className="panel overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
            <h3 className="text-[13.5px] font-semibold text-ink">Ayrıntılı tablo</h3>
            <span className="text-[12.5px] text-muted">{gorunen.length.toLocaleString('tr-TR')} satır</span>
            <label className="relative ml-auto">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted" />
              <input value={ara} onChange={(e) => setAra(e.target.value)} placeholder="Tabloda ara" aria-label="Tabloda ara" className={cn(inputCls, 'h-8 w-56 pl-8 text-[13px]')} />
            </label>
          </div>
          <div className="scroll-thin max-h-[70vh] overflow-auto">
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 z-10 bg-surface-2 text-[12px] text-ink-2">
                <tr>
                  <th className="w-10 px-3 py-2 text-right font-medium">#</th>
                  <Baslik ad={`${etiket(k.boyut)}${k.seri ? ` · ${etiket(k.seri)}` : ''}`} k="d0" sira={sira} setSira={setSira} sol />
                  {sutunlar.map((s) => <Baslik key={s.key} ad={s.ad} k={s.key} sira={sira} setSira={setSira} />)}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {gorunen.map((r, i) => (
                  <tr key={anahtar(r)} className="hover:bg-surface-2/60">
                    <td className="tnum px-3 py-1.5 text-right text-muted">{i + 1}</td>
                    <td className="max-w-[320px] truncate px-3 py-1.5 text-ink" title={String(r._etiket)}>{String(r._etiket)}</td>
                    {sutunlar.map((s) => (
                      <td key={s.key} className={cn('tnum px-3 py-1.5 text-right whitespace-nowrap', s.key === mk ? 'font-semibold text-ink' : 'text-ink-2',
                        s.key === '_degisim' && isNum(r._degisim) && (Number(r._degisim) >= 0 ? 'text-pos' : 'text-neg'))}>
                        {s.key === '_degisim'
                          ? (isNum(r._degisim) ? `${Number(r._degisim) >= 0 ? '+' : '−'}${Math.abs(Number(r._degisim)).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}${tip === 'pct' ? ' p' : '%'}` : '—')
                          : s.key === '_pay' ? (isNum(r._pay) ? `%${Number(r._pay).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}` : '—')
                            : isNum(r[s.key]) ? fmt(r[s.key], s.tip) : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              {veri && !ara && (
                <tfoot className="sticky bottom-0 bg-surface-2 text-[13px] font-semibold text-ink">
                  <tr>
                    <td /><td className="px-3 py-2">Toplam</td>
                    {sutunlar.map((s) => (
                      <td key={s.key} className="tnum px-3 py-2 text-right whitespace-nowrap">
                        {s.key.startsWith('m_') ? fmt(veri.sonuc.totals[s.key], s.tip) : s.key === '_pay' ? '%100' : s.key === '_onceki' && !zaman ? fmt(onceki, tip) : ''}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

function Kutu({ ad, deger, alt }: { ad: string; deger: string; alt?: React.ReactNode }) {
  return (
    <div className="panel px-4 py-3">
      <p className="truncate text-[12px] text-muted first-letter:uppercase">{ad}</p>
      <p className="display tnum mt-1 truncate text-[20px] leading-tight font-semibold text-ink" title={deger}>{deger}</p>
      {alt && <p className="mt-0.5 truncate text-[12.5px] text-ink-2">{alt}</p>}
    </div>
  )
}

function Baslik({ ad, k, sira, setSira, sol }: { ad: string; k: string; sira: { key: string; desc: boolean }; setSira: (s: { key: string; desc: boolean }) => void; sol?: boolean }) {
  const aktif = sira.key === k
  return (
    <th className={cn('px-3 py-2 font-medium whitespace-nowrap', sol ? 'text-left' : 'text-right')}
      aria-sort={aktif ? (sira.desc ? 'descending' : 'ascending') : 'none'}>
      <button onClick={() => setSira({ key: k, desc: aktif ? !sira.desc : k !== 'd0' })}
        className={cn('inline-flex items-center gap-1 hover:text-ink', aktif && 'text-ink')}>
        {ad}{aktif && (sira.desc ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
      </button>
    </th>
  )
}
