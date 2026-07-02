export interface LiveDashboardTabItem {
  id: string;
  label: string;
  count?: number;
}

interface LiveDashboardTabsProps {
  tabs: LiveDashboardTabItem[];
  activeId: string;
  onChange: (id: string) => void;
}

export function LiveDashboardTabs({ tabs, activeId, onChange }: LiveDashboardTabsProps) {
  return (
    <div className="live-dashboard-tabs mx-2 sm:mx-4">
      <nav
        className="live-dashboard-tabs-track"
        aria-label="Seções do dashboard ao vivo"
      >
        {tabs.map((tab) => {
          const isActive = activeId === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onChange(tab.id)}
              aria-current={isActive ? "page" : undefined}
              className={`live-tab-btn ${isActive ? "live-tab-active" : "live-tab-idle"}`}
            >
              <span className="truncate">{tab.label}</span>
              {tab.count != null && tab.count > 0 && (
                <span className={`live-tab-count ${isActive ? "is-active" : ""}`}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
