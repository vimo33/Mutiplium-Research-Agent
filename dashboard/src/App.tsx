import { useState, useEffect, useCallback, useMemo } from "react";
import { Sidebar } from "./components/Sidebar";
import { DeepResearchView } from "./components/DeepResearchView";
import { DiscoveryView } from "./components/DiscoveryView";
import { RunsView } from "./components/RunsView";
import "./App.css";

// Local storage key for shortlist persistence
const SHORTLIST_STORAGE_KEY = "multiplium_shortlist";

// Default segments for wine value chain
const DEFAULT_SEGMENTS = [
  "Grape Production (Viticulture)",
  "Wine Production (Vinification)",
  "Packaging & Bottling",
  "Distribution & Logistics",
  "Retail & Sales",
  "Marketing & Branding",
  "Consumption",
  "Recycling & Aftermarket",
];

export default function App() {
  // View state
  const [currentView, setCurrentView] = useState<string>("research");
  
  // Segment filter state
  const [selectedSegments, setSelectedSegments] = useState<string[]>(DEFAULT_SEGMENTS);
  
  // Shortlist state (persisted to localStorage)
  const [shortlistedCompanies, setShortlistedCompanies] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(SHORTLIST_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Persist shortlist to localStorage
  useEffect(() => {
    localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlistedCompanies));
  }, [shortlistedCompanies]);

  // Segment toggle handlers
  const handleSegmentToggle = useCallback((segment: string) => {
    setSelectedSegments(prev =>
      prev.includes(segment)
        ? prev.filter(s => s !== segment)
        : [...prev, segment]
    );
  }, []);

  const handleSelectAllSegments = useCallback(() => {
    setSelectedSegments(DEFAULT_SEGMENTS);
  }, []);

  const handleClearSegments = useCallback(() => {
    setSelectedSegments([]);
  }, []);

  // Shortlist handlers
  const handleToggleShortlist = useCallback((company: string) => {
    setShortlistedCompanies(prev =>
      prev.includes(company)
        ? prev.filter(c => c !== company)
        : [...prev, company]
    );
  }, []);

  const handleClearShortlist = useCallback(() => {
    setShortlistedCompanies([]);
  }, []);

  const handleShortlistClick = useCallback((company: string) => {
    // Could navigate to the company in the research view
    setCurrentView("research");
    // TODO: Could set a selected company state to auto-open that company's detail panel
  }, []);

  // Render current view
  const renderView = () => {
    switch (currentView) {
      case "runs":
        return <RunsView />;
      case "discovery":
        return (
          <DiscoveryView
            selectedSegments={selectedSegments}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
      case "research":
      default:
        return (
          <DeepResearchView
            selectedSegments={selectedSegments}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        currentView={currentView}
        onViewChange={setCurrentView}
        segments={DEFAULT_SEGMENTS}
        selectedSegments={selectedSegments}
        onSegmentToggle={handleSegmentToggle}
        onSelectAllSegments={handleSelectAllSegments}
        onClearSegments={handleClearSegments}
        shortlistedCompanies={shortlistedCompanies}
        onShortlistClick={handleShortlistClick}
        onClearShortlist={handleClearShortlist}
      />
      <main className="app-main">
        <div className="app-content">
          {renderView()}
        </div>
      </main>
    </div>
  );
}
