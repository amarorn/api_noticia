import type { SuperbetLiveAdvice } from "@/domain/entities";
import {
  sportradarLmtEmbedUrl,
  useSportradarConfig,
} from "@/presentation/hooks/useSportradarConfig";
import "./SportradarLmtWidget.css";

interface SportradarLmtWidgetProps {
  data: SuperbetLiveAdvice;
  className?: string;
}

/**
 * Widget Sportradar match.lmtPlus via iframe — mesmo feed Betradar da Superbet.
 * O client id fica no backend (.env SPORTRADAR_CLIENT_ID); atualização em tempo real é do SR.
 */
export function SportradarLmtWidget({ data, className = "" }: SportradarLmtWidgetProps) {
  const { data: cfg, isLoading } = useSportradarConfig();

  if (!data.betradarId) {
    return (
      <div className={`sr-lmt-placeholder ${className}`}>
        <p className="sr-lmt-placeholder__title">Tracker ao vivo indisponível</p>
        <p className="sr-lmt-placeholder__text">
          Este evento Superbet não tem <code>betradar_id</code> — sem vínculo ao feed Sportradar.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return <div className={`sr-lmt-skeleton ${className}`} aria-hidden />;
  }

  if (!cfg?.embedAvailable) {
    return (
      <div className={`sr-lmt-placeholder ${className}`}>
        <p className="sr-lmt-placeholder__title">Licença Sportradar necessária</p>
        <p className="sr-lmt-placeholder__text">
          Para o campo idêntico ao da Superbet (feed Betradar em tempo real), configure{" "}
          <code>SPORTRADAR_CLIENT_ID</code> no <code>.env</code> da API e reinicie o servidor.
        </p>
        <p className="sr-lmt-placeholder__meta">
          Betradar matchId: <code>{data.betradarId}</code>
        </p>
      </div>
    );
  }

  return (
    <div className={`sr-lmt-frame-wrap ${className}`}>
      <iframe
        key={data.betradarId}
        title={`Sportradar LMT · ${data.homeTeam} x ${data.awayTeam}`}
        src={sportradarLmtEmbedUrl(data.betradarId)}
        className="sr-lmt-frame"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  );
}

/** Tracker oficial Sportradar (sem réplica local). */
export function LiveMatchTracker(props: SportradarLmtWidgetProps) {
  return <SportradarLmtWidget {...props} />;
}
