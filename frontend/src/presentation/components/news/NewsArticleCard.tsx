import { motion } from "framer-motion";
import type { NewsArticle } from "@/domain/entities";
import { SentimentBadge } from "./SentimentBadge";
import { formatRelativeTime } from "@/presentation/utils/formatRelativeTime";
import { sourceStyles } from "@/presentation/utils/newsSources";

interface NewsArticleCardProps {
  article: NewsArticle;
  index?: number;
  featured?: boolean;
}

export function NewsArticleCard({
  article,
  index = 0,
  featured = false,
}: NewsArticleCardProps) {
  const accent = sourceStyles(article.source);
  const when = formatRelativeTime(article.publishedAt ?? article.scrapedAt);

  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      whileHover={{ y: featured ? -2 : -4 }}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-surface-card backdrop-blur-xl transition-all duration-300 hover:border-white/20 hover:shadow-neon-blue ${
        featured ? "md:min-h-[320px]" : ""
      }`}
    >
      <div
        className={`pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-neon-green/60 via-neon-blue/60 to-neon-purple/60 opacity-0 transition-opacity group-hover:opacity-100 ${
          featured ? "opacity-80" : ""
        }`}
      />

      <div className={`flex flex-1 flex-col p-5 ${featured ? "sm:p-7" : ""}`}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-lg border px-2.5 py-0.5 text-[11px] font-semibold ${accent.bg} ${accent.text} ${accent.border}`}
          >
            {article.sourceName}
          </span>
          <SentimentBadge label={article.sentimentLabel} />
          <span className="ml-auto text-[11px] text-slate-500">{when}</span>
        </div>

        <h3
          className={`font-bold leading-snug text-white transition-colors group-hover:text-neon-blue/90 ${
            featured ? "text-xl sm:text-2xl" : "text-base line-clamp-3"
          }`}
        >
          {article.title}
        </h3>

        <p
          className={`mt-3 flex-1 text-slate-400 ${
            featured ? "text-sm leading-relaxed line-clamp-4 sm:line-clamp-5" : "text-sm line-clamp-3"
          }`}
        >
          {article.bodyPreview}
        </p>

        {article.teamsMentioned.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {article.teamsMentioned.slice(0, 4).map((team) => (
              <span
                key={team}
                className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-300"
              >
                {team}
              </span>
            ))}
            {article.teamsMentioned.length > 4 && (
              <span className="text-[11px] text-slate-500">
                +{article.teamsMentioned.length - 4}
              </span>
            )}
          </div>
        )}

        <a
          href={article.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-ghost mt-5 w-full justify-center gap-2 text-xs group-hover:border-neon-blue/30"
        >
          Ler na fonte
          <svg
            className="h-3.5 w-3.5 opacity-70"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden
          >
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3" />
          </svg>
        </a>
      </div>
    </motion.article>
  );
}
