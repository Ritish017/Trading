import React from 'react';
import { MarketNarrativeBanner } from '../intelligence/MarketNarrativeBanner';
import { IntelligenceTimeline } from '../intelligence/IntelligenceTimeline';
import { SecurityIntelligencePanel } from '../intelligence/SecurityIntelligencePanel';
import { MarketNarrative, MarketEvent, AICommentary } from '../../types/intelligence';
import { NSEStock } from '../../types/indianMarket';

interface IntelligenceDeskPageProps {
  narrative?: MarketNarrative;
  isNarrativeLoading?: boolean;
  onRefreshNarrative?: () => void;
  events: MarketEvent[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  selectedStock?: NSEStock;
  commentary?: AICommentary;
  isCommentaryLoading?: boolean;
  onRefreshCommentary?: () => void;
}

export const IntelligenceDeskPage: React.FC<IntelligenceDeskPageProps> = ({
  narrative,
  isNarrativeLoading,
  onRefreshNarrative,
  events,
  selectedSymbol,
  onSelectSymbol,
  selectedStock,
  commentary,
  isCommentaryLoading,
  onRefreshCommentary,
}) => {
  return (
    <div className="flex-1 p-3 flex flex-col space-y-3 h-[calc(100vh-175px)] overflow-y-auto custom-scrollbar">
      {/* Top Banner: Today's Market Narrative */}
      {narrative && (
        <MarketNarrativeBanner
          narrative={narrative}
          isLoading={isNarrativeLoading}
          onRefresh={onRefreshNarrative}
        />
      )}

      {/* Main Grid: Left Event Stream Timeline & Right Comprehensive Evidence Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 flex-1 min-h-[550px]">
        {/* Left Column (Col 4): Apex Intelligence Event Timeline */}
        <div className="md:col-span-4 flex flex-col h-full min-h-[450px]">
          <IntelligenceTimeline
            events={events}
            selectedSymbol={selectedSymbol}
            onSelectSymbol={onSelectSymbol}
          />
        </div>

        {/* Right Column (Col 8): Security Intelligence Panel */}
        <div className="md:col-span-8 flex flex-col h-full overflow-y-auto custom-scrollbar">
          <SecurityIntelligencePanel
            commentary={commentary}
            isLoading={isCommentaryLoading}
            onRefresh={onRefreshCommentary}
          />
        </div>
      </div>
    </div>
  );
};
