import { FictionalBadge } from '../components/FictionalBadge'

export function PlaceholderPage({ title, blurb }: { title: string; blurb: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-8">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-neutral-900">{title}</h2>
        <FictionalBadge />
      </div>
      <p className="mt-3 max-w-xl text-sm text-neutral-500">{blurb}</p>
      <p className="mt-6 text-sm text-navy-600">Coming next from the feature PRD — platform auth is live.</p>
    </div>
  )
}
