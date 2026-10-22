/*
  Yorum motoru: bir kartin sonucunu sunumda okunacak Turkce cumlelere cevirir.
  Yapay zeka gerekmez; kurallar istatistik temellidir (zirve, dip, trend,
  olagandisi donem, yogunlasma, onceki donemle kiyas). Ileride API anahtari
  girildiginde ayni yapiya gercek yapay zeka yorumu eklenecek.
*/
import type { ColType, QueryResult } from './api'
import { fmtShort, isNum } from './format'

export type Ton = 'notr' | 'iyi' | 'kotu' | 'dikkat'
export interface Cumle { metin: string; ton: Ton }

const AY = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
const ZAMAN = new Set(['day', 'week', 'month', 'quarter', 'year', 'weekday'])

export function donemAdi(k: unknown, dim?: string): string {
  const s = String(k ?? '')
  if (dim === 'month' && /^\d{4}-\d{2}$/.test(s)) { const [y, m] = s.split('-'); return `${AY[Number(m) - 1]} ${y}` }
  if (dim === 'quarter') return s.replace('-Ç', ' yılının ') + (s.includes('-Ç') ? '. çeyreği' : '')
  if (dim === 'day' && /^\d{4}-\d{2}-\d{2}$/.test(s)) { const [y, m, d] = s.split('-'); return `${Number(d)} ${AY[Number(m) - 1]} ${y}` }
  if (dim === 'week') return `${s} haftası`
  if (dim === 'weekday') return s.replace(/^\d\s/, '')
  return s
}

const yuzde = (x: number) => `%${Math.abs(x).toLocaleString('tr-TR', { maximumFractionDigits: x < 10 && x > -10 ? 1 : 0 })}`
const deger = (v: number, tip: ColType) => (tip === 'pct' ? `%${v.toLocaleString('tr-TR', { maximumFractionDigits: 1 })}` : fmtShort(v, tip))

function trend(y: number[]) {
  // basit dogrusal regresyon egimi, ortalamaya gore donem basina yuzde
  const n = y.length
  const mx = (n - 1) / 2, my = y.reduce((a, b) => a + b, 0) / n
  let pay = 0, payda = 0
  y.forEach((v, i) => { pay += (i - mx) * (v - my); payda += (i - mx) ** 2 })
  return my ? (pay / payda / Math.abs(my)) * 100 : 0
}

export interface YorumGirdi {
  olcuAdi: string; tip: ColType; mkey: string
  boyut?: string; boyutAdi?: string; seri?: string
  sonuc: QueryResult; onceki?: QueryResult
  surucu?: { donem: string; satirlar: { ad: string; deger: number }[]; toplam: number }
  aralikAdi: string
  sonDonemSuruyor?: boolean        // aralik bugunu kapsiyorsa son donem eksik
  tatiller?: { date: string; ad: string }[]   // resmi tatiller (Nager.Date); olagandisi donemi aciklamak icin
}

/** Bir ay/gun dilimine denk gelen resmi tatiller: " (bu dönemde Kurban Bayramı var)". */
function tatilNotu(key: unknown, boyut: string | undefined, tatiller?: { date: string; ad: string }[]) {
  if (!tatiller?.length || !boyut) return ''
  const k = String(key ?? '')
  let icinde: (d: string) => boolean
  if (boyut === 'month' && /^\d{4}-\d{2}$/.test(k)) icinde = (d) => d.startsWith(k)
  else if (boyut === 'day') icinde = (d) => d === k
  else if (boyut === 'quarter' && k.includes('-Ç')) {
    const [y, q] = k.split('-Ç').map(Number)
    icinde = (d) => Number(d.slice(0, 4)) === y && Math.ceil(Number(d.slice(5, 7)) / 3) === q
  } else return ''
  // Yalnizca gecmis ve cok gunlu bayramlar (Ramazan, Kurban) satisi gercekten etkiler
  const bugun = new Date().toISOString().slice(0, 10)
  const adlar = [...new Set(tatiller.filter((t) => t.date <= bugun && icinde(t.date) && /Ramazan|Kurban/.test(t.ad))
    .map((t) => t.ad.replace(/\s*\d+\.\s*Gün$/, '').replace(/\s*Arifesi$/, '').trim()))]
  if (!adlar.length) return ''
  return ` Bu dönemde ${adlar.join(' ve ')} tatili var; iş günü sayısı azalmış olabilir.`
}

export function yorumla(g: YorumGirdi): Cumle[] {
  const c: Cumle[] = []
  const anilan = new Set<string>()
  const tatil = (key: unknown) => { const k = String(key); if (anilan.has(k)) return ''; const n = tatilNotu(key, g.boyut, g.tatiller); if (n) anilan.add(k); return n }
  const toplam = g.sonuc.totals?.[g.mkey]
  const oncekiToplam = g.onceki?.totals?.[g.mkey]
  const oran = g.tip === 'pct'

  // --- tek sayi ya da genel toplam + onceki donem
  if (isNum(toplam)) {
    let m = `${g.aralikAdi} döneminde ${g.olcuAdi.toLocaleLowerCase('tr')} ${deger(toplam, g.tip)}.`
    let ton: Ton = 'notr'
    if (isNum(oncekiToplam) && oncekiToplam !== 0) {
      if (oran) {
        const fark = toplam - oncekiToplam
        m += ` Bir önceki eşit dönemde ${deger(oncekiToplam, g.tip)} idi; ${Math.abs(fark).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} puan ${fark >= 0 ? 'yükseldi' : 'düştü'}.`
        ton = fark >= 0 ? 'iyi' : 'kotu'
      } else {
        const d = ((toplam - oncekiToplam) / Math.abs(oncekiToplam)) * 100
        m += ` Bir önceki eşit döneme göre ${yuzde(d)} ${d >= 0 ? 'artış' : 'düşüş'} var (${deger(oncekiToplam, g.tip)}).`
        ton = Math.abs(d) < 3 ? 'notr' : d >= 0 ? 'iyi' : 'kotu'
      }
    }
    c.push({ metin: m, ton })
  }
  if (!g.boyut) return c

  const satirlar = g.sonuc.rows.filter((r) => isNum(r[g.mkey]))
  if (!satirlar.length) { c.push({ metin: 'Bu aralıkta veri yok; tarih aralığını ya da seçimleri genişletmeyi deneyin.', ton: 'dikkat' }); return c }

  if (ZAMAN.has(g.boyut) && !g.seri) {
    const s = [...satirlar].sort((a, b) => String(a.d0).localeCompare(String(b.d0)))
    const y = s.map((r) => Number(r[g.mkey]))
    const ort = y.reduce((a, b) => a + b, 0) / y.length
    const sd = Math.sqrt(y.reduce((a, b) => a + (b - ort) ** 2, 0) / y.length)
    const iMax = y.indexOf(Math.max(...y)), iMin = y.indexOf(Math.min(...y))
    if (y.length >= 3) {
      c.push({ metin: `En güçlü dönem ${donemAdi(s[iMax].d0, g.boyut)} (${deger(y[iMax], g.tip)}), en zayıf dönem ${donemAdi(s[iMin].d0, g.boyut)} (${deger(y[iMin], g.tip)}).${oran ? '' : tatil(s[iMin].d0)}`, ton: 'notr' })
      const t = trend(y)
      if (Math.abs(t) >= 1.5) c.push({ metin: `Genel eğilim ${t > 0 ? 'yukarı' : 'aşağı'} yönlü: dönem başına ortalama ${yuzde(t)} ${t > 0 ? 'büyüme' : 'gerileme'}.`, ton: t > 0 ? 'iyi' : 'kotu' })
      else c.push({ metin: 'Dönemler arasında belirgin bir yükseliş ya da düşüş eğilimi yok; seyir yatay.', ton: 'notr' })
      // olagandisi donemler
      if (sd > 0 && !oran) {
        const sapan = s.map((r, i) => ({ r, z: (y[i] - ort) / sd, v: y[i] })).filter((x) => Math.abs(x.z) >= 1.8)
        for (const x of sapan.slice(0, 2)) {
          const fark = ((x.v - ort) / Math.abs(ort)) * 100
          c.push({ metin: `${donemAdi(x.r.d0, g.boyut)} önemli bir aralık: ortalamanın ${yuzde(fark)} ${fark > 0 ? 'üstünde' : 'altında'}${fark > 0 ? ', olağan dışı bir sıçrama' : ', olağan dışı bir düşüş'}.${fark < 0 ? tatil(x.r.d0) : ''}`, ton: 'dikkat' })
        }
      }
      // son donem
      const son = y[y.length - 1], once = y[y.length - 2]
      if (isNum(once) && once !== 0 && !oran) {
        const d = ((son - once) / Math.abs(once)) * 100
        if (Math.abs(d) >= 10) c.push({ metin: `Son dönem (${donemAdi(s[s.length - 1].d0, g.boyut)}) bir öncekine göre ${yuzde(d)} ${d > 0 ? 'yukarıda' : 'aşağıda'}${g.sonDonemSuruyor ? '; ancak bu dönem henüz bitmedi' : ''}.${d < 0 ? tatil(s[s.length - 1].d0) : ''}`, ton: d > 0 ? 'iyi' : 'kotu' })
      }
    }
    if (g.surucu && g.surucu.satirlar.length && g.surucu.toplam > 0) {
      const ilk = g.surucu.satirlar[0]
      const pay = (ilk.deger / g.surucu.toplam) * 100
      const ilk3 = g.surucu.satirlar.slice(0, 3).reduce((a, b) => a + b.deger, 0) / g.surucu.toplam * 100
      c.push(pay >= 25
        ? { metin: `${donemAdi(g.surucu.donem, g.boyut)} zirvesi büyük ölçüde tek müşteriye bağlı: ${ilk.ad}, o dönemin ${yuzde(pay)} payını tek başına aldı. Bu müşteri çıkarıldığında zirve belirgin şekilde küçülür.`, ton: 'dikkat' }
        : { metin: `${donemAdi(g.surucu.donem, g.boyut)} zirvesi geniş tabanlı; en büyük katkı ${ilk.ad} (${yuzde(pay)}), ilk üç müşterinin payı ${yuzde(ilk3)}.`, ton: 'iyi' })
    }
    return c
  }

  // --- kategori kirilimi
  const s = [...satirlar].sort((a, b) => Number(b[g.mkey]) - Number(a[g.mkey]))
  const ad = (r: Record<string, unknown>) => donemAdi(r.d0, g.boyut)
  if (oran) {
    c.push({ metin: `En yüksek ${g.olcuAdi.toLocaleLowerCase('tr')} ${ad(s[0])} (${deger(Number(s[0][g.mkey]), g.tip)}), en düşük ${ad(s[s.length - 1])} (${deger(Number(s[s.length - 1][g.mkey]), g.tip)}).`, ton: 'notr' })
    return c
  }
  const genel = s.reduce((a, r) => a + Number(r[g.mkey]), 0)
  if (genel > 0) {
    const p1 = (Number(s[0][g.mkey]) / genel) * 100
    c.push({ metin: `${g.boyutAdi ?? 'Kırılımda'} lider ${ad(s[0])}; toplamdaki payı ${yuzde(p1)} (${deger(Number(s[0][g.mkey]), g.tip)}).`, ton: p1 >= 40 ? 'dikkat' : 'notr' })
    if (s.length >= 5) {
      const p3 = (s.slice(0, 3).reduce((a, r) => a + Number(r[g.mkey]), 0) / genel) * 100
      c.push({ metin: p3 >= 60
        ? `İlk üç kalemin payı ${yuzde(p3)}; gelir birkaç kaleme yoğunlaşmış, bu bir bağımlılık riski.`
        : `İlk üç kalemin payı ${yuzde(p3)}; dağılım ${s.length} kaleme yayılmış durumda.`, ton: p3 >= 60 ? 'dikkat' : 'notr' })
    }
    if (s.length >= 2) {
      const fark = Number(s[0][g.mkey]) / Math.max(Number(s[1][g.mkey]), 1)
      if (fark >= 2) c.push({ metin: `Lider, ikinci sıradakinin (${ad(s[1])}) ${fark.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} katı büyüklükte.`, ton: 'notr' })
    }
  }
  return c
}
