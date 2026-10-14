import { GROUPS, stageOf, TAB_LABEL, TAB_PURPOSE, type Tab } from './nav'

function Mark() {
  // two legs under a block: the creature, reduced to what the physics model actually has
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect x="9" y="3" width="14" height="11" rx="3" fill="var(--create)" />
      <path d="M12 14 L10 23 L5 27 M20 14 L22 23 L27 27" stroke="var(--txt)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}

export function Shell({ tab, go }: { tab: Tab; go: (t: Tab) => void }) {
  const stage = stageOf(tab)
  const group = GROUPS.find((g) => g.id === stage)!
  return (
    <>
      <header className="shell">
        <button className="brand" onClick={() => go('overview')} aria-label="Creature Forge home"><Mark /><span>Creature Forge</span></button>
        <nav className="journey" aria-label="Create, simulate, investigate">
          {GROUPS.map((g) => (
            <button key={g.id} style={{ ['--c' as string]: g.color }} aria-current={g.id === stage ? 'page' : undefined} data-testid={`nav-${g.id}`}
              onClick={() => go(g.id === stage ? tab : g.tabs[0])}>
              <span className="dot" />{g.label}
            </button>
          ))}
        </nav>
      </header>
      {tab !== 'overview' && (
        <div className="subnav" data-testid="subnav">
          {group.tabs.length > 1 && (
            <div className="seg" role="tablist" aria-label={`${group.label} views`}>
              {group.tabs.map((t) => (
                <button key={t} role="tab" aria-selected={t === tab} data-testid={`tab-${t}`} onClick={() => go(t)}>{TAB_LABEL[t]}</button>
              ))}
            </div>
          )}
          <span className="lede" data-testid="purpose">{TAB_PURPOSE[tab]}</span>
        </div>
      )}
    </>
  )
}
