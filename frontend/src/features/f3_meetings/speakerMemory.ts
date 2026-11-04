const STORAGE_KEY = 'meeting_known_speakers'

function isGenericLabel(name: string): boolean {
  return /^person\s*\d+$/i.test(name.trim())
}

export function loadKnownSpeakers(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((item) => String(item).trim())
      .filter((name) => name && !isGenericLabel(name))
  } catch {
    return []
  }
}

export function saveKnownSpeakers(names: string[]): string[] {
  const existing = loadKnownSpeakers()
  const merged = [...existing]
  for (const name of names) {
    const clean = name.trim()
    if (!clean || isGenericLabel(clean)) continue
    const exists = merged.some((item) => item.toLowerCase() === clean.toLowerCase())
    if (!exists) merged.push(clean)
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  return merged
}

export function clearKnownSpeakers(): void {
  sessionStorage.removeItem(STORAGE_KEY)
}

export function extractSpeakerNamesFromTranscript(transcript: string): string[] {
  const names: string[] = []
  const pattern = /^([A-Za-z][A-Za-z.'\- ]{0,40}):\s*$/gm
  let match: RegExpExecArray | null = pattern.exec(transcript)
  while (match) {
    const name = match[1].trim()
    if (name && !isGenericLabel(name)) {
      const exists = names.some((item) => item.toLowerCase() === name.toLowerCase())
      if (!exists) names.push(name)
    }
    match = pattern.exec(transcript)
  }
  return names
}

/**
 * Replace named speakers (David, Robbie, ...) with Person 1, Person 2, ...
 * in order of first appearance.
 */
export function anonymizeSpeakersInTranscript(transcript: string): string {
  const labelPattern = /^([A-Za-z][A-Za-z0-9.'\- ]{0,40}):\s*$/gm
  const order: string[] = []
  let match: RegExpExecArray | null = labelPattern.exec(transcript)
  while (match) {
    const label = match[1].trim()
    if (label && !order.some((item) => item.toLowerCase() === label.toLowerCase())) {
      order.push(label)
    }
    match = labelPattern.exec(transcript)
  }

  if (order.length === 0) return transcript

  const mapping = new Map(order.map((label, index) => [label.toLowerCase(), `Person ${index + 1}`]))

  return transcript.replace(
    /^([A-Za-z][A-Za-z0-9.'\- ]{0,40}):\s*$/gm,
    (_full, label: string) => {
      const mapped = mapping.get(label.trim().toLowerCase())
      return `${mapped ?? label}:`
    },
  )
}
