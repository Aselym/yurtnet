import { useEffect, useRef, useState } from 'react'
import { FileSpreadsheet, FileUp, Info, Loader2, Receipt, Trash2 } from 'lucide-react'
import { api, ApiError, type ActionResult } from '../lib/api'
import { fmt } from '../lib/format'
import { Badge, Button, cn, inputCls, toast } from './ui'

/*
  Veri baglama: Excel/CSV ya da e-Fatura. Kolonlar otomatik eslenir, her
  oneri guven puani ve gerekcesiyle gosterilir; kullanici duzeltip onaylar.
  Dosya sirketin kendi sunucusuna yuklenir, baska yere gitmez.
*/

interface Oneri { kolon: number; guven: number; neden: string }
interface Analiz {
  dosya: string; sayfalar: string[]; sayfa: string; basliklar: string[]; onizleme: string[][]; ornekler: string[][]
  oneri: Record<string, Oneri>; eksik: string[]; alanlar: { key: string; label: string; zorunlu: boolean }[]
  kayitli?: Record<string, number>
}
interface EOzet {
  faturalar: number; satirlar?: number; sirket_vkn?: string | null; sirket_ad?: string | null; sirket_orani?: number
  satis?: number; alis?: number; ilk?: string | null; son?: string | null; dovizli?: number; okunamayan?: number; dosyalar: string[]
}

async function yukle<T>(dosya: File): Promise<T> {
  const res = await fetch('/api/kaynak/yukle', {
    method: 'POST', credentials: 'include', body: dosya,
    headers: { 'Content-Type': 'application/octet-stream', 'X-Dosya-Adi': encodeURIComponent(dosya.name) },
  })
  const veri = await res.json().catch(() => ({}))
  if (!res.ok || veri.success === false) throw new ApiError(res.status, veri.message || `Yükleme başarısız (${res.status})`)
  return veri as T
}

function Birakma({ kabul, coklu, metin, alt, onDosyalar, mesgul }: {
  kabul: string; coklu?: boolean; metin: string; alt: string; onDosyalar: (f: File[]) => void; mesgul: boolean
}) {
  const [ust, setUst] = useState(false)
  const ref = useRef<HTMLInputElement>(null)
  return (
    <button type="button" onClick={() => ref.current?.click()} disabled={mesgul}
      onDragOver={(e) => { e.preventDefault(); setUst(true) }} onDragLeave={() => setUst(false)}
      onDrop={(e) => { e.preventDefault(); setUst(false); if (e.dataTransfer.files.length) onDosyalar([...e.dataTransfer.files]) }}
      className={cn('flex w-full flex-col items-center justify-center gap-1.5 rounded-[var(--radius-panel)] border border-dashed px-6 py-8 text-center transition-colors',
        ust ? 'border-brand bg-brand-soft' : 'border-line-strong bg-surface-2 hover:border-ink-2')}>
      {mesgul ? <Loader2 className="size-6 animate-spin text-muted" /> : <FileUp className="size-6 text-muted" />}
      <span className="text-[14px] font-medium text-ink">{mesgul ? 'Okunuyor ve çözümleniyor…' : metin}</span>
      <span className="text-[12.5px] text-muted">{alt}</span>
      <input ref={ref} type="file" accept={kabul} multiple={coklu} className="sr-only"
        onChange={(e) => { if (e.target.files?.length) onDosyalar([...e.target.files]); e.target.value = '' }} />
    </button>
  )
}

function GuvenEtiketi({ o }: { o?: Oneri }) {
  if (!o) return <span className="text-[12px] text-muted">elle seçildi</span>
  const ton = o.guven >= 0.8 ? 'good' : o.guven >= 0.6 ? 'warning' : 'serious'
  return (
    <span title={o.neden} className="inline-flex cursor-help items-center gap-1">
      <Badge tone={ton}>%{Math.round(o.guven * 100)}</Badge>
    </span>
  )
}

// ------------------------------------------------------------------ Excel / CSV
export function TabloBaglayici({ mevcutDosya, onBitti }: { mevcutDosya?: string | null; onBitti: () => void }) {
  const [a, setA] = useState<Analiz | null>(null)
  const [es, setEs] = useState<Record<string, number | ''>>({})
  const [yon, setYon] = useState('SATIS')
  const [mesgul, setMesgul] = useState(false)
  const [kaydediyor, setKaydediyor] = useState(false)

  const uygula = (r: Analiz) => {
    setA(r)
    const kayitli = r.kayitli
    setEs(Object.fromEntries(r.alanlar.map((f) => [f.key, kayitli ? (kayitli[f.key] ?? '') : (r.oneri[f.key]?.kolon ?? '')])))
  }
  useEffect(() => {
    if (!mevcutDosya) return
    api.post<Analiz & ActionResult>('/api/kaynak/analiz', {}).then(uygula, () => {})
  }, [mevcutDosya])

  const dosyaSec = async (f: File[]) => {
    setMesgul(true)
    try { uygula(await yukle<Analiz>(f[0])) } catch (e) { toast.err(e instanceof Error ? e.message : 'Yüklenemedi.') } finally { setMesgul(false) }
  }
  const sayfaSec = async (sayfa: string) => {
    if (!a) return
    setMesgul(true)
    try { uygula(await api.post<Analiz>('/api/kaynak/analiz', { dosya: a.dosya, sayfa })) } finally { setMesgul(false) }
  }
  const onayla = async () => {
    if (!a) return
    setKaydediyor(true)
    try {
      const r = await api.post<ActionResult>('/api/kaynak/esleme', { dosya: a.dosya, sayfa: a.sayfa, esleme: es, varsayilan_yon: yon })
      toast.ok(r.message)
      onBitti()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setKaydediyor(false) }
  }

  const eksik = a ? a.alanlar.filter((f) => f.zorunlu && es[f.key] === '' && !(f.key === 'tutar' && es.birim_fiyat !== '')) : []
  const otomatik = a ? Object.keys(a.oneri).length : 0

  return (
    <div className="flex flex-col gap-5">
      <Birakma kabul=".xlsx,.xlsm,.csv,.txt,.tsv" metin={a ? 'Başka bir dosya yükle' : 'Excel ya da CSV dosyasını buraya bırakın ya da seçin'}
        alt="Muhasebe programından alınmış satış/alış listesi. Üstteki başlık satırlarını ve kolon adlarını program kendisi çözer."
        onDosyalar={dosyaSec} mesgul={mesgul} />

      {a && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-[14px]">
              <FileSpreadsheet className="size-4 text-muted" /><b className="font-semibold">{a.dosya}</b>
              <span className="text-ink-2">— {a.basliklar.length} kolon, {otomatik} tanesi otomatik eşlendi</span>
            </p>
            {a.sayfalar.length > 1 && (
              <label className="flex items-center gap-2 text-[13px] text-ink-2">Sayfa
                <select value={a.sayfa} onChange={(e) => sayfaSec(e.target.value)} className={cn(inputCls, 'h-8 w-auto py-0 text-[13px]')}>
                  {a.sayfalar.map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
            )}
          </div>

          <div className="overflow-hidden rounded-[var(--radius-panel)] border border-line">
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full min-w-[640px] text-[13px]">
                <thead className="bg-surface-2 text-left text-ink-2">
                  <tr><th className="px-4 py-2 font-medium">Tailglass alanı</th><th className="font-medium">Dosyadaki kolon</th>
                    <th className="font-medium">Güven</th><th className="pr-4 font-medium">Örnek değerler</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {a.alanlar.map((f) => {
                    const k = es[f.key]
                    const o = a.oneri[f.key]
                    const otoMu = o && o.kolon === k
                    return (
                      <tr key={f.key} className={cn(f.zorunlu && k === '' && 'bg-[color-mix(in_oklab,var(--critical)_6%,transparent)]')}>
                        <td className="px-4 py-2 font-medium whitespace-nowrap">{f.label}{f.zorunlu && <span className="ml-1 text-neg" title="Zorunlu">*</span>}</td>
                        <td className="py-1.5 pr-3">
                          <select value={k === '' ? '' : String(k)} onChange={(e) => setEs({ ...es, [f.key]: e.target.value === '' ? '' : Number(e.target.value) })}
                            className={cn(inputCls, 'h-8 w-56 py-0 text-[13px]')}>
                            <option value="">— eşleme yok —</option>
                            {a.basliklar.map((b, i) => <option key={i} value={i}>{b}</option>)}
                          </select>
                        </td>
                        <td className="py-1.5 pr-3">{k === '' ? <span className="text-muted">—</span> : <GuvenEtiketi o={otoMu ? o : undefined} />}</td>
                        <td className="max-w-[320px] truncate py-1.5 pr-4 text-ink-2">{k === '' ? '' : (a.ornekler[k as number] || []).join(', ')}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {es.yon === '' && (
            <label className="flex flex-wrap items-center gap-2 text-[13.5px] text-ink-2">
              İşlem türü kolonu yok; dosyadaki bütün satırlar
              <select value={yon} onChange={(e) => setYon(e.target.value)} className={cn(inputCls, 'h-8 w-auto py-0 text-[13px]')}>
                <option value="SATIS">satış</option><option value="ALIS">alış</option>
              </select>
              sayılsın. Eksi tutarlar iade sayılır.
            </label>
          )}

          <details className="text-[13px]">
            <summary className="cursor-pointer text-ink-2 hover:text-ink">Dosyanın ilk satırlarını göster</summary>
            <div className="scroll-thin mt-2 overflow-x-auto rounded-[var(--radius-panel)] border border-line">
              <table className="text-[12.5px]">
                <thead className="bg-surface-2 text-left text-ink-2"><tr>{a.basliklar.map((b, i) => <th key={i} className="px-3 py-1.5 font-medium whitespace-nowrap">{b}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">{a.onizleme.map((r, i) => <tr key={i}>{a.basliklar.map((_, j) => <td key={j} className="px-3 py-1.5 whitespace-nowrap">{r[j]}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </details>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" loading={kaydediyor} disabled={eksik.length > 0} onClick={onayla}>Eşlemeyi onayla ve içe aktar</Button>
            {eksik.length > 0
              ? <span className="text-[13px] text-neg">Eksik: {eksik.map((f) => f.label).join(', ')}</span>
              : <span className="inline-flex items-center gap-1.5 text-[12.5px] text-muted"><Info className="size-3.5" />Güven puanının üstüne gelince eşlemenin gerekçesi görünür.</span>}
          </div>
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ e-Fatura
export function EFaturaBaglayici({ onBitti }: { onBitti: () => void }) {
  const [oz, setOz] = useState<EOzet | null>(null)
  const [vkn, setVkn] = useState('')
  const [mesgul, setMesgul] = useState(false)
  const [kaydediyor, setKaydediyor] = useState(false)

  const ozetAl = async (v?: string) => {
    const r = await api.post<EOzet>('/api/kaynak/efatura-ozet', v ? { vkn: v } : {})
    setOz(r.faturalar ? r : null)
    if (r.sirket_vkn) setVkn(r.sirket_vkn)
  }
  useEffect(() => { ozetAl().catch(() => {}) }, [])

  const dosyalar = async (fs: File[]) => {
    setMesgul(true)
    try {
      for (const f of fs) await yukle<EOzet>(f)
      await ozetAl()
      toast.ok(`${fs.length} dosya yüklendi.`)
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Yüklenemedi.') } finally { setMesgul(false) }
  }
  const temizle = async () => {
    await api.del('/api/kaynak/efatura')
    setOz(null); setVkn('')
  }
  const onayla = async () => {
    setKaydediyor(true)
    try {
      const r = await api.post<ActionResult>('/api/kaynak/efatura-onayla', { vkn })
      toast.ok(r.message)
      onBitti()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setKaydediyor(false) }
  }

  return (
    <div className="flex flex-col gap-5">
      <Birakma kabul=".xml,.zip" coklu metin={oz ? 'Daha fazla e-Fatura ekle' : 'e-Fatura XML ya da ZIP arşivlerini buraya bırakın'}
        alt="Entegratörünüzden ya da GİB portalından indirilen gelen ve giden faturalar (UBL-TR). Aylık arşivleri tek tek ekleyebilirsiniz."
        onDosyalar={dosyalar} mesgul={mesgul} />

      {oz && (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-panel)] border border-line bg-line md:grid-cols-4">
            {[
              ['Fatura', fmt(oz.faturalar, 'num'), `${fmt(oz.satirlar, 'num')} satır`],
              ['Satış / alış', `${fmt(oz.satis, 'num')} / ${fmt(oz.alis, 'num')}`, 'şirketin satıcı ya da alıcı olduğu'],
              ['Tarih aralığı', oz.ilk ? `${oz.ilk.split('-').reverse().join('.')}` : '—', oz.son ? `${oz.son.split('-').reverse().join('.')} tarihine kadar` : ''],
              ['Dövizli fatura', fmt(oz.dovizli, 'num'), 'faturadaki kurla TL’ye çevrilir'],
            ].map(([l, v, alt]) => (
              <div key={l} className="bg-surface px-4 py-3">
                <p className="text-[12.5px] text-ink-2">{l}</p>
                <p className="tnum mt-0.5 text-[18px] font-semibold">{v}</p>
                <p className="text-[12px] text-muted">{alt}</p>
              </div>
            ))}
          </div>

          <div className="rounded-[var(--radius-panel)] border border-line bg-surface-2 p-4 text-[13.5px]">
            <p className="flex items-center gap-2 font-medium text-ink"><Receipt className="size-4 text-muted" />
              Şirketiniz: {oz.sirket_ad || 'bulunamadı'}</p>
            <p className="mt-1 text-ink-2">
              Faturaların %{Math.round((oz.sirket_orani ?? 0) * 100)}'inde geçen vergi numarası şirketin kendisi kabul edildi.
              Satıcı sizseniz fatura satış, alıcı sizseniz alış sayılır. Yanlışsa vergi numarasını düzeltin.
            </p>
            <label className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-ink-2">Vergi / TC kimlik no</span>
              <input value={vkn} onChange={(e) => setVkn(e.target.value.replace(/\D/g, ''))} onBlur={() => ozetAl(vkn).catch(() => {})}
                className={cn(inputCls, 'h-8 w-44 py-0 text-[13px]')} />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" loading={kaydediyor} onClick={onayla} disabled={!vkn}>e-Fatura'yı veri kaynağı yap</Button>
            <Button variant="ghost" icon={<Trash2 className="size-4" />} onClick={temizle}>Yüklenen dosyaları kaldır</Button>
            <span className="text-[12.5px] text-muted">{oz.dosyalar.length} dosya{oz.okunamayan ? `, ${oz.okunamayan} okunamayan XML atlandı` : ''}</span>
          </div>
        </>
      )}
    </div>
  )
}
