export function formatYmd(ymd: string | null | undefined): string {
  if (!ymd) return '-'
  const digits = ymd.replace(/\D/g, '')
  if (digits.length !== 8) return ymd
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`
}

export function formatIsoDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

export function formatArea(area: number | null | undefined): string {
  if (area === null || area === undefined) return '-'
  return `${area.toLocaleString('ko-KR', { maximumFractionDigits: 1 })} ㎡`
}

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined) return '-'
  return `${value.toLocaleString('ko-KR')}${suffix}`
}
