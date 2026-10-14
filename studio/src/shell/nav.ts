// Information architecture: Create -> Simulate -> Investigate (plus Home). Every legacy ?tab= value still resolves.
export type Tab = 'overview' | 'studio' | 'compare' | 'lab' | 'locomotion' | 'demo' | 'sketch'
export type Stage = 'home' | 'create' | 'simulate' | 'investigate'

export const ALL_TABS: Tab[] = ['overview', 'sketch', 'studio', 'compare', 'demo', 'locomotion', 'lab']

export const TAB_LABEL: Record<Tab, string> = {
  overview: 'Home', sketch: 'Draw', studio: 'Playground', compare: 'Compare designs',
  demo: 'AI investigation', locomotion: 'Walking lab', lab: 'Experiment history',
}

export const TAB_PURPOSE: Record<Tab, string> = {
  overview: '',
  sketch: 'Draw a two-legged creature with the pen. Creature Forge reads your strokes and builds it in the physics engine.',
  studio: 'Drop a creature into the simulator, push it, and see exactly when and why it falls.',
  compare: 'The same push on two creatures that differ in one thing: foot length.',
  demo: 'Watch an AI model look at a real failure, propose a change, and let the simulator judge it.',
  locomotion: 'See a walking robot before and after it was tuned, then check the numbers.',
  lab: 'Every earlier AI-assisted experiment, sorted by what happened to it.',
}

export const GROUPS: { id: Stage; label: string; color: string; tabs: Tab[] }[] = [
  { id: 'home', label: 'Home', color: 'var(--simulate)', tabs: ['overview'] },
  { id: 'create', label: 'Create', color: 'var(--create)', tabs: ['sketch'] },
  { id: 'simulate', label: 'Simulate', color: 'var(--simulate)', tabs: ['studio', 'compare'] },
  { id: 'investigate', label: 'Investigate', color: 'var(--investigate)', tabs: ['demo', 'locomotion', 'lab'] },
]

export const stageOf = (t: Tab): Stage => GROUPS.find((g) => g.tabs.includes(t))!.id

export function parseTab(search: string): Tab {
  const t = new URLSearchParams(search).get('tab')
  return (ALL_TABS as string[]).includes(t ?? '') ? (t as Tab) : 'overview'
}
