import React from 'react';
import { Lightbulb, ThumbsUp, TrendingUp } from 'lucide-react';
import { HealthScore } from '../../types';
import { METRIC_LABELS, METRIC_ORDER, gradeTone } from './healthGrades';
import { EmptyState, SectionLabel } from './primitives';

const Bullets: React.FC<{
  title: string;
  icon: React.ReactNode;
  items: string[];
  tone: string;
}> = ({ title, icon, items, tone }) => {
  if (items.length === 0) return null;
  return (
    <div className="space-y-2 border-t border-black/5 pt-4">
      <span className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-brand-graphite/40">
        <span className={tone}>{icon}</span>
        {title}
      </span>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-1.5 text-[11px] leading-relaxed text-brand-graphite/70">
            <span className={`mt-1 h-1 w-1 shrink-0 rounded-full ${tone.replace('text-', 'bg-')}`} />
            <span className="min-w-0 break-words">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export const HealthAnalysis: React.FC<{ health: HealthScore }> = ({ health }) => {
  const tone = gradeTone(health.grade);

  return (
    <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
      <SectionLabel className="block">Health Analysis</SectionLabel>

      {!health.has_data ? (
        <EmptyState message="Upload your financial data to calculate your health score." />
      ) : (
        <>
          <div className="flex items-center gap-3">
            <span className="font-serif text-4xl font-light tabular-nums text-brand-navy">
              {health.score.toFixed(1)}
            </span>
            <div className="flex min-w-0 flex-col">
              <span className={`text-xs font-bold tracking-wider ${tone.text}`}>
                {health.grade_label}
              </span>
              <span className="text-[10px] text-brand-graphite/40">Weighted across 6 metrics</span>
            </div>
          </div>

          <div
            className="h-2 w-full overflow-hidden rounded-full bg-black/5"
            role="progressbar"
            aria-valuenow={Math.round(health.score)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Financial health score"
          >
            <div
              className={`h-full rounded-full transition-all duration-500 ${tone.bar}`}
              style={{ width: `${Math.max(0, Math.min(100, health.score))}%` }}
            />
          </div>

          {/* Every metric, with the weight it actually carried in the score. */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-black/5 pt-4">
            {METRIC_ORDER.map((key) => {
              const metric = health.breakdown[key];
              if (!metric) return null;
              const unmeasured = metric.weight === 0;
              return (
                <div key={key} className="min-w-0 space-y-0.5" title={metric.explanation}>
                  <span className="block text-[9px] font-bold uppercase tracking-widest text-brand-graphite/40">
                    {METRIC_LABELS[key]}
                    <span className="ml-1 font-semibold normal-case tracking-normal text-brand-graphite/30">
                      {unmeasured ? 'n/a' : `${metric.weight}%`}
                    </span>
                  </span>
                  <span
                    className={`block font-serif text-base font-semibold leading-tight ${
                      unmeasured ? 'text-brand-graphite/35' : 'text-brand-navy'
                    }`}
                  >
                    {metric.raw_value}
                  </span>
                  <span className="block text-[9px] text-brand-graphite/40">
                    Target {metric.target}
                  </span>
                </div>
              );
            })}
          </div>

          <Bullets
            title="Strengths"
            icon={<ThumbsUp size={11} />}
            items={health.strengths}
            tone="text-emerald-600"
          />
          <Bullets
            title="Areas to Improve"
            icon={<TrendingUp size={11} />}
            items={health.areas_to_improve}
            tone="text-amber-600"
          />
          <Bullets
            title="AI Financial Insights"
            icon={<Lightbulb size={11} />}
            items={health.insights}
            tone="text-[#c09a5f]"
          />
          <Bullets
            title="Recommendations"
            icon={<Lightbulb size={11} />}
            items={health.recommendations}
            tone="text-brand-navy"
          />
        </>
      )}
    </div>
  );
};
